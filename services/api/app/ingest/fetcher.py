"""Kurallara uyan HTTP istemcisi: izin listesi, robots.txt, sunucu başına hız ve boyut sınırı."""

import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from app.ingest.sources_config import SourcesConfig

logger = logging.getLogger(__name__)

MAX_REDIRECTS = 5
SUPPORTED_TYPES = ("text/html", "application/xhtml+xml", "application/pdf")


class FetchError(Exception):
    """Kaynak çekilemedi. `reason` kısa, makine tarafından okunabilir bir koddur."""

    def __init__(self, reason: str, detail: str = "", status_code: int | None = None):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.status_code = status_code


class NotAllowedError(FetchError):
    def __init__(self, url: str):
        super().__init__("not_allowed", f"izin listesinde değil: {url}")


class RobotsDisallowedError(FetchError):
    def __init__(self, url: str):
        super().__init__("robots_disallowed", f"robots.txt izin vermiyor: {url}")


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str  # "text/html" veya "application/pdf"
    content: bytes
    charset: str | None = None  # HTTP başlığındaki karakter kodlaması


class _AllowAll:
    def can_fetch(self, useragent: str, url: str) -> bool:
        return True

    def crawl_delay(self, useragent: str) -> None:
        return None


class _DenyAll(_AllowAll):
    def can_fetch(self, useragent: str, url: str) -> bool:
        return False


class PoliteFetcher:
    def __init__(
        self,
        config: SourcesConfig,
        client: httpx.Client | None = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        max_bytes: int = 25 * 1024 * 1024,
        max_retries: int = 2,
        timeout: float = 60.0,
    ):
        self.config = config
        self.client = client or httpx.Client(timeout=timeout)
        self._clock = clock
        self._sleep = sleep
        self.max_bytes = max_bytes
        self.max_retries = max_retries
        self._robots: dict[str, RobotFileParser | _AllowAll] = {}
        self._last_request: dict[str, float] = {}

    @property
    def _headers(self) -> dict[str, str]:
        return {"User-Agent": self.config.user_agent, "Accept-Language": "tr-TR,tr;q=0.9"}

    # --- robots.txt ---

    def _robots_for(self, url: str) -> RobotFileParser | _AllowAll:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            self._robots[origin] = self._load_robots(origin)
        return self._robots[origin]

    def _load_robots(self, origin: str) -> RobotFileParser | _AllowAll:
        robots_url = origin + "/robots.txt"
        try:
            self._throttle(robots_url)
            response = self.client.get(robots_url, headers=self._headers, follow_redirects=True)
        except httpx.HTTPError as exc:
            # RFC 9309: robots.txt'ye ulaşılamıyorsa site tamamen kapalı kabul edilir.
            logger.warning("robots.txt alınamadı (%s): %s", robots_url, type(exc).__name__)
            return _DenyAll()
        if response.status_code >= 500:
            return _DenyAll()
        if response.status_code >= 400:
            return _AllowAll()  # robots.txt yok: kısıtlama yok
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser

    def robots_allows(self, url: str) -> bool:
        return self._robots_for(url).can_fetch(self.config.user_agent, url)

    # --- hız sınırı ---

    def _delay_for(self, url: str) -> float:
        delay = self.config.min_delay_seconds
        parts = urlsplit(url)
        robots = self._robots.get(f"{parts.scheme}://{parts.netloc}")
        crawl_delay = robots.crawl_delay(self.config.user_agent) if robots else None
        return max(delay, float(crawl_delay or 0))

    def _throttle(self, url: str) -> None:
        host = urlsplit(url).netloc
        last = self._last_request.get(host)
        if last is not None:
            wait = self._delay_for(url) - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)
        self._last_request[host] = self._clock()

    # --- çekme ---

    def fetch(self, url: str) -> FetchResult:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            if not self.config.is_allowed(current):
                raise NotAllowedError(current)
            if not self.robots_allows(current):
                raise RobotsDisallowedError(current)

            status, headers, body = self._get_with_retries(current)
            if status in (301, 302, 303, 307, 308) and "location" in headers:
                current = urljoin(current, headers["location"])
                continue
            if status != 200:
                raise FetchError("http_error", f"HTTP {status}", status_code=status)
            return FetchResult(
                url=url,
                final_url=current,
                status_code=status,
                content_type=_detect_type(headers.get("content-type", ""), body),
                content=body,
                charset=_charset(headers.get("content-type", "")),
            )
        raise FetchError("too_many_redirects", url)

    def _get_with_retries(self, url: str) -> tuple[int, httpx.Headers, bytes]:
        attempt = 0
        while True:
            self._throttle(url)
            try:
                with self.client.stream("GET", url, headers=self._headers) as response:
                    if response.status_code in (429, 500, 502, 503, 504):
                        raise _Retryable(f"HTTP {response.status_code}", response.status_code)
                    body = self._read_limited(response)
                    return response.status_code, response.headers, body
            except (httpx.TransportError, _Retryable) as exc:
                if attempt >= self.max_retries:
                    status = exc.status_code if isinstance(exc, _Retryable) else None
                    raise FetchError("unreachable", type(exc).__name__, status_code=status) from exc
                attempt += 1
                self._sleep(self.config.min_delay_seconds * 2**attempt)

    def _read_limited(self, response: httpx.Response) -> bytes:
        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_bytes():
            size += len(chunk)
            if size > self.max_bytes:
                raise FetchError("too_large", f"> {self.max_bytes} bayt")
            chunks.append(chunk)
        return b"".join(chunks)


class _Retryable(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


def _charset(content_type: str) -> str | None:
    match = re.search(r"charset=[\"']?([\w-]+)", content_type, re.I)
    return match.group(1).lower() if match else None


def _detect_type(content_type: str, body: bytes) -> str:
    if body.startswith(b"%PDF"):
        return "application/pdf"
    mime = content_type.split(";")[0].strip().lower()
    if mime in SUPPORTED_TYPES:
        return "text/html" if mime == "application/xhtml+xml" else mime
    raise FetchError("unsupported_content_type", mime or "bilinmiyor")

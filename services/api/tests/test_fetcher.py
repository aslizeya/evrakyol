from collections.abc import Callable

import httpx
import pytest

from app.ingest.fetcher import (
    FetchError,
    NotAllowedError,
    PoliteFetcher,
    RobotsDisallowedError,
)
from app.ingest.sources_config import SourcesConfig

HTML = b"<html><body><p>Merhaba</p></body></html>"
ROBOTS = "User-agent: *\nDisallow: /gizli\n"


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


def make_fetcher(
    config: SourcesConfig,
    handler: Callable[[httpx.Request], httpx.Response],
    clock: FakeClock | None = None,
    **kwargs,
) -> tuple[PoliteFetcher, list[str]]:
    requested: list[str] = []

    def recording(request: httpx.Request) -> httpx.Response:
        requested.append(str(request.url))
        return handler(request)

    clock = clock or FakeClock()
    fetcher = PoliteFetcher(
        config,
        httpx.Client(transport=httpx.MockTransport(recording)),
        clock=clock,
        sleep=clock.sleep,
        **kwargs,
    )
    return fetcher, requested


def site(routes: dict[str, httpx.Response]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(request.url.path, httpx.Response(404))

    return handler


def html_response(body: bytes = HTML) -> httpx.Response:
    return httpx.Response(200, content=body, headers={"content-type": "text/html; charset=utf-8"})


def test_fetches_allowed_page_and_sends_user_agent(sources_config: SourcesConfig) -> None:
    seen_agents = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_agents.append(request.headers["user-agent"])
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=ROBOTS)
        return html_response()

    fetcher, _ = make_fetcher(sources_config, handler)
    result = fetcher.fetch("https://example.gov.tr/sayfa")

    assert result.content == HTML
    assert result.content_type == "text/html"
    assert set(seen_agents) == {"EvrakyolBot/test"}


def test_rejects_url_outside_allowlist_without_any_request(sources_config: SourcesConfig) -> None:
    fetcher, requested = make_fetcher(sources_config, site({}))
    with pytest.raises(NotAllowedError):
        fetcher.fetch("https://baska-site.com/sayfa")
    assert requested == []


def test_respects_robots_disallow(sources_config: SourcesConfig) -> None:
    fetcher, requested = make_fetcher(
        sources_config, site({"/robots.txt": httpx.Response(200, text=ROBOTS)})
    )
    with pytest.raises(RobotsDisallowedError):
        fetcher.fetch("https://example.gov.tr/gizli/belge")
    assert requested == ["https://example.gov.tr/robots.txt"]


def test_missing_robots_means_no_restrictions(sources_config: SourcesConfig) -> None:
    fetcher, _ = make_fetcher(sources_config, site({"/sayfa": html_response()}))
    assert fetcher.fetch("https://example.gov.tr/sayfa").status_code == 200


def test_unreachable_robots_means_full_disallow(sources_config: SourcesConfig) -> None:
    fetcher, _ = make_fetcher(
        sources_config,
        site({"/robots.txt": httpx.Response(503), "/sayfa": html_response()}),
    )
    with pytest.raises(RobotsDisallowedError):
        fetcher.fetch("https://example.gov.tr/sayfa")


def test_waits_between_requests_to_same_host(sources_config: SourcesConfig) -> None:
    clock = FakeClock()
    fetcher, _ = make_fetcher(
        sources_config, site({"/a": html_response(), "/b": html_response()}), clock
    )
    fetcher.fetch("https://example.gov.tr/a")
    fetcher.fetch("https://example.gov.tr/b")
    # robots.txt, /a ve /b arasında en az 3 saniye beklenir
    assert clock.sleeps == [3, 3]


def test_honours_longer_crawl_delay(sources_config: SourcesConfig) -> None:
    clock = FakeClock()
    robots = httpx.Response(200, text="User-agent: *\nCrawl-delay: 10\n")
    fetcher, _ = make_fetcher(
        sources_config,
        site({"/robots.txt": robots, "/a": html_response(), "/b": html_response()}),
        clock,
    )
    fetcher.fetch("https://example.gov.tr/a")
    fetcher.fetch("https://example.gov.tr/b")
    assert clock.sleeps[-1] == 10


def test_does_not_follow_redirect_outside_allowlist(sources_config: SourcesConfig) -> None:
    fetcher, requested = make_fetcher(
        sources_config,
        site({"/yonlendir": httpx.Response(302, headers={"location": "https://kotu.com/x"})}),
    )
    with pytest.raises(NotAllowedError):
        fetcher.fetch("https://example.gov.tr/yonlendir")
    assert not any("kotu.com" in url for url in requested)


def test_follows_redirect_within_allowlist(sources_config: SourcesConfig) -> None:
    fetcher, _ = make_fetcher(
        sources_config,
        site(
            {
                "/eski": httpx.Response(
                    301, headers={"location": "https://www.example.gov.tr/yeni"}
                ),
                "/yeni": html_response(),
            }
        ),
    )
    result = fetcher.fetch("https://example.gov.tr/eski")
    assert result.final_url == "https://www.example.gov.tr/yeni"


def test_retries_server_errors_then_fails(sources_config: SourcesConfig) -> None:
    fetcher, requested = make_fetcher(sources_config, site({"/sayfa": httpx.Response(503)}))
    with pytest.raises(FetchError) as exc_info:
        fetcher.fetch("https://example.gov.tr/sayfa")
    assert exc_info.value.reason == "unreachable"
    assert requested.count("https://example.gov.tr/sayfa") == 3  # ilk deneme + 2 tekrar


def test_rejects_too_large_response(sources_config: SourcesConfig) -> None:
    fetcher, _ = make_fetcher(
        sources_config, site({"/buyuk": html_response(b"x" * 2000)}), max_bytes=1000
    )
    with pytest.raises(FetchError) as exc_info:
        fetcher.fetch("https://example.gov.tr/buyuk")
    assert exc_info.value.reason == "too_large"


def test_detects_pdf_by_magic_bytes(sources_config: SourcesConfig) -> None:
    pdf = httpx.Response(
        200, content=b"%PDF-1.7 ...", headers={"content-type": "application/octet-stream"}
    )
    fetcher, _ = make_fetcher(sources_config, site({"/dosya": pdf}))
    assert fetcher.fetch("https://example.gov.tr/dosya").content_type == "application/pdf"


def test_rejects_unsupported_content_type(sources_config: SourcesConfig) -> None:
    image = httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})
    fetcher, _ = make_fetcher(sources_config, site({"/resim": image}))
    with pytest.raises(FetchError) as exc_info:
        fetcher.fetch("https://example.gov.tr/resim")
    assert exc_info.value.reason == "unsupported_content_type"

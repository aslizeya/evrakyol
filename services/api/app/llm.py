"""Sağlayıcıdan bağımsız LLM katmanı.

Uygulamanın geri kalanı yalnızca `LLMProvider.generate_json` arayüzünü bilir; sağlayıcı
`LLM_PROVIDER` ortam değişkeniyle seçilir. Şu an tek gerçek sağlayıcı Anthropic Claude'dur.
"""

import logging
import threading
from dataclasses import dataclass
from datetime import UTC, date, datetime
from functools import lru_cache
from typing import Protocol

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0


class LLMError(Exception):
    """LLM çağrısı başarısız. `reason`: refusal, max_tokens, rate_limited, unavailable,
    auth, billing, bad_request, api_error, budget_exceeded, not_configured, empty."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason


class LLMProvider(Protocol):
    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, object],
        max_tokens: int = 32000,
        effort: str | None = None,
    ) -> LLMResponse:
        """`schema`'ya uyan tek bir JSON nesnesini metin olarak döndürür. `effort` verilmezse
        sağlayıcının varsayılanı kullanılır."""
        ...


class AnthropicProvider:
    # Haiku'da sunucu tarafı yedek model (fallbacks) yoktur.
    _NO_FALLBACK_PREFIXES = ("claude-haiku",)

    def __init__(
        self,
        *,
        api_key: str | None,
        model: str,
        effort: str = "high",
        use_fallbacks: bool = True,
        client: anthropic.Anthropic | None = None,
    ):
        if client is None and not api_key:
            raise LLMError("not_configured", "ANTHROPIC_API_KEY tanımlı değil")
        # Akış (streaming) kullanıldığı için zaman aşımı, toplam süre değil iki veri parçası
        # arasındaki bekleme süresidir. Tekrar sayısı düşük tutulur: web katmanı en fazla
        # ~150 sn bekler, daha uzun süren tekrarlar kullanıcıya ulaşmadan ücretlendirilir.
        self.client = client or anthropic.Anthropic(
            api_key=api_key, max_retries=1, timeout=anthropic.Timeout(90, connect=10)
        )
        self.model = model
        self.effort = effort
        self.use_fallbacks = use_fallbacks and not model.startswith(self._NO_FALLBACK_PREFIXES)

    def generate_json(
        self,
        *,
        system: str,
        user: str,
        schema: dict[str, object],
        max_tokens: int = 32000,
        effort: str | None = None,
    ) -> LLMResponse:
        extra: dict[str, object] = {}
        if self.use_fallbacks:
            # Güvenlik sınıflandırıcısı reddederse istek, reddin türüne göre önerilen modelde
            # sunucu tarafında yeniden çalıştırılır.
            extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
        try:
            # Düşünme bu modelde her zaman açıktır ve `max_tokens`'a dahildir; sınır bu yüzden
            # yanıtın kendisinden çok daha geniş tutulur. Uzun isteklerde bağlantının boşta
            # kalıp kopmaması için akış kullanılır.
            with self.client.beta.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                # Sabit sistem talimatı önbelleklenir; değişken kaynaklar kullanıcı mesajındadır.
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=[{"role": "user", "content": user}],
                output_config={
                    "effort": effort or self.effort,
                    "format": {"type": "json_schema", "schema": schema},
                },
                **extra,
            ) as stream:
                response = stream.get_final_message()
        except anthropic.RateLimitError as exc:
            raise LLMError("rate_limited") from exc
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise LLMError(
                "auth", f"HTTP {exc.status_code}: API anahtarı geçersiz veya yetkisiz"
            ) from exc
        except anthropic.BadRequestError as exc:
            # Örn. yetersiz bakiye veya geçersiz istek; ayrıntı yalnızca sunucu kaydına yazılır.
            reason = "billing" if "credit balance" in str(exc.message).lower() else "bad_request"
            raise LLMError(reason, f"HTTP 400: {exc.message}") from exc
        except anthropic.APIStatusError as exc:
            raise LLMError("api_error", f"HTTP {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError("unavailable", type(exc).__name__) from exc

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            raise LLMError("refusal", str(category or ""))
        if response.stop_reason == "max_tokens":
            raise LLMError("max_tokens")
        text = "".join(block.text for block in response.content if block.type == "text")
        if not text.strip():
            raise LLMError("empty")
        usage = response.usage
        return LLMResponse(
            text=text,
            model=response.model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=usage.cache_read_input_tokens or 0,
        )


class DailyLimitedProvider:
    """Günlük çağrı tavanı (maliyet koruması). Sayaç süreç içidir; birden çok örnekte
    her örnek kendi tavanını uygular."""

    def __init__(self, inner: LLMProvider, daily_limit: int):
        self.inner = inner
        self.daily_limit = daily_limit
        self._day: date | None = None
        self._count = 0
        self._lock = threading.Lock()

    def generate_json(self, **kwargs) -> LLMResponse:
        with self._lock:
            today = datetime.now(UTC).date()
            if self._day != today:
                self._day, self._count = today, 0
            if self._count >= self.daily_limit:
                raise LLMError("budget_exceeded", f"günlük {self.daily_limit} çağrı tavanı")
            self._count += 1
        return self.inner.generate_json(**kwargs)


class FakeProvider:
    """Testler için: sıradaki yanıtı (metin veya hata) döndürür ve çağrıları kaydeder."""

    def __init__(self, responses: list[str | Exception]):
        self.responses = list(responses)
        self.calls: list[dict[str, object]] = []

    def generate_json(self, **kwargs) -> LLMResponse:
        self.calls.append(kwargs)
        if not self.responses:
            raise AssertionError("FakeProvider: beklenmeyen ek çağrı")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return LLMResponse(text=item, model="fake")


@lru_cache
def get_llm() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider != "anthropic":
        raise LLMError("not_configured", f"bilinmeyen sağlayıcı: {settings.llm_provider}")
    provider = AnthropicProvider(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        effort=settings.llm_effort,
        use_fallbacks=settings.llm_fallbacks,
    )
    return DailyLimitedProvider(provider, settings.llm_daily_request_limit)

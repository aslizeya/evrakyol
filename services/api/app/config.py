from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SERVICE_DIR.parent.parent


class Settings(BaseSettings):
    """Servis ayarları: ortam değişkenlerinden ve kök klasördeki `.env` dosyasından okunur."""

    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", SERVICE_DIR / ".env"),
        extra="ignore",
    )

    # Veritabanı gerektirmeyen komutlar (ör. `python -m app.ingest preview`) için isteğe bağlı.
    database_url: str | None = Field(default=None, description="Postgres bağlantı adresi")
    internal_api_token: str | None = None
    config_dir: Path = REPO_ROOT / "config"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    # "fake": modelsiz deterministik vektörler (test ve hızlı deneme için)
    embedding_backend: Literal["bge", "fake"] = "bge"
    # "memory": veritabanı olmadan, kaynakları canlı çekip bellekte arar (yalnızca yerel deneme)
    retriever_backend: Literal["db", "memory"] = "db"
    log_level: str = "info"

    # LLM (sağlayıcıdan bağımsız katman, app/llm.py)
    llm_provider: Literal["anthropic"] = "anthropic"
    llm_model: str = "claude-opus-5-5"
    # Yol haritası üretimi için; sınıflandırma basit bir iş olduğundan daha düşük düzeyde çalışır
    llm_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"
    llm_understanding_effort: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    # Güvenlik sınıflandırıcısı reddederse sunucu tarafında önerilen yedek modelle yeniden dene
    llm_fallbacks: bool = True
    llm_daily_request_limit: int = 100
    anthropic_api_key: str | None = None
    # Uydurma yargıcı: test edilen modelden farklı olmalı (kendi çıktısını kayırmasın)
    eval_judge_model: str = "claude-sonnet-5-5"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str | None) -> str | None:
        if value is None:
            return None
        # Web (Prisma) ile aynı `postgresql://` adresi kullanılabilsin diye sürücü burada eklenir.
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

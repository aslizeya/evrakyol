from functools import lru_cache
from pathlib import Path

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

    database_url: str = Field(description="Postgres bağlantı adresi")
    internal_api_token: str | None = None
    config_dir: Path = REPO_ROOT / "config"
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    log_level: str = "info"

    @field_validator("database_url")
    @classmethod
    def _use_psycopg_driver(cls, value: str) -> str:
        # Web (Prisma) ile aynı `postgresql://` adresi kullanılabilsin diye sürücü burada eklenir.
        for prefix in ("postgresql://", "postgres://"):
            if value.startswith(prefix):
                return "postgresql+psycopg://" + value[len(prefix) :]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]

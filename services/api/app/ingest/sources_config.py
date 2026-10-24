import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, Field, field_validator

from app.config import get_settings

_ARTICLE_RANGE = re.compile(r"^\d+(-\d+)?$")


class SourceOptions(BaseModel):
    """Kaynağa özgü ayıklama seçenekleri. Veritabanında `kb.sources.options` olarak saklanır."""

    legislation: bool = False
    articles: list[str] | None = None

    @field_validator("articles")
    @classmethod
    def _valid_ranges(cls, value: list[str] | None) -> list[str] | None:
        for item in value or []:
            if not _ARTICLE_RANGE.match(item):
                raise ValueError(f"Geçersiz madde aralığı: {item!r} (örn. '598' veya '495-501')")
        return value


class AllowedDomain(BaseModel):
    domain: str = Field(pattern=r"^[a-z0-9.-]+\.[a-z]{2,}$")
    institution: str


class SourceSeed(BaseModel):
    url: str
    institution: str
    title: str | None = None
    process_codes: list[str] = Field(min_length=1)
    options: SourceOptions = SourceOptions()


class SourcesConfig(BaseModel):
    user_agent: str
    min_delay_seconds: float = Field(ge=1)
    reject_patterns: list[str] = []
    allowed_domains: list[AllowedDomain] = Field(min_length=1)
    sources: list[SourceSeed] = []

    def is_allowed(self, url: str) -> bool:
        """Yalnızca izin listesindeki alan adlarına (ve alt alanlarına) giden HTTPS adresleri."""
        parts = urlsplit(url)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
            return False
        if parts.port not in (None, 443):
            return False
        host = parts.hostname.lower().rstrip(".")
        return any(host == d.domain or host.endswith("." + d.domain) for d in self.allowed_domains)

    def institution_for(self, url: str) -> str | None:
        host = (urlsplit(url).hostname or "").lower()
        for d in self.allowed_domains:
            if host == d.domain or host.endswith("." + d.domain):
                return d.institution
        return None


def load_sources_config(path: Path) -> SourcesConfig:
    return SourcesConfig.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


@lru_cache
def get_sources_config() -> SourcesConfig:
    return load_sources_config(get_settings().config_dir / "sources.yaml")

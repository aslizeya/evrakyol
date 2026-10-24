import pytest
from pydantic import ValidationError

from app.config import REPO_ROOT
from app.ingest.sources_config import SourceOptions, SourcesConfig, load_sources_config
from app.process_types import load_process_types


@pytest.mark.parametrize(
    ("url", "allowed"),
    [
        ("https://example.gov.tr/sayfa", True),
        ("https://www.example.gov.tr/sayfa", True),
        ("https://portal.tnb.org.tr/Sayfalar/MirascilikHiz.aspx", True),
        ("http://example.gov.tr/sayfa", False),  # yalnızca HTTPS
        ("https://kotu-example.gov.tr/sayfa", False),  # benzer ama farklı alan adı
        ("https://example.gov.tr.saldirgan.com/", False),
        ("https://user:pass@example.gov.tr/", False),
        ("https://example.gov.tr:8443/", False),
        ("https://baska.gov.tr/", False),
        ("ftp://example.gov.tr/", False),
        ("not a url", False),
    ],
)
def test_allowlist(sources_config: SourcesConfig, url: str, allowed: bool) -> None:
    assert sources_config.is_allowed(url) is allowed


def test_institution_lookup(sources_config: SourcesConfig) -> None:
    assert (
        sources_config.institution_for("https://portal.tnb.org.tr/x") == "Türkiye Noterler Birliği"
    )
    assert sources_config.institution_for("https://baska.gov.tr/") is None


def test_article_ranges_validated() -> None:
    assert SourceOptions(articles=["495-501", "598"]).articles == ["495-501", "598"]
    with pytest.raises(ValidationError):
        SourceOptions(articles=["598a"])


def test_repository_config_is_consistent() -> None:
    """config/sources.yaml: her kaynak izin listesinde ve geçerli işlem kodlarına bağlı olmalı."""
    config = load_sources_config(REPO_ROOT / "config" / "sources.yaml")
    known_codes = {p.code for p in load_process_types(REPO_ROOT / "config")}
    urls = [s.url for s in config.sources]

    assert len(urls) == len(set(urls)), "Aynı kaynak iki kez tanımlanmış"
    for source in config.sources:
        assert config.is_allowed(source.url), source.url
        assert set(source.process_codes) <= known_codes, source.url

    covered = {code for s in config.sources for code in s.process_codes}
    assert {"miras_arac_devri", "mirascilik_belgesi"} <= covered

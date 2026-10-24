import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.ingest.sources_config import AllowedDomain, SourcesConfig


@pytest.fixture
def sources_config() -> SourcesConfig:
    return SourcesConfig(
        user_agent="EvrakyolBot/test",
        min_delay_seconds=3,
        reject_patterns=["Henüz kimliğinizi doğrulamadınız"],
        allowed_domains=[
            AllowedDomain(domain="example.gov.tr", institution="Örnek Kurum"),
            AllowedDomain(domain="tnb.org.tr", institution="Türkiye Noterler Birliği"),
        ],
    )


@pytest.fixture(scope="session")
def migrated_engine() -> Engine:
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL tanımlı değil")
    from alembic import command
    from alembic.config import Config

    from app.config import SERVICE_DIR
    from app.db import get_engine

    command.upgrade(Config(str(SERVICE_DIR / "alembic.ini")), "head")
    return get_engine()


@pytest.fixture
def db_sessionmaker(migrated_engine: Engine) -> Iterator[sessionmaker[Session]]:
    with migrated_engine.begin() as conn:
        conn.execute(
            text("TRUNCATE kb.chunks, kb.ingestion_logs, kb.sources RESTART IDENTITY CASCADE")
        )
    yield sessionmaker(bind=migrated_engine, expire_on_commit=False)

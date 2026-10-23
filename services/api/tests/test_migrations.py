"""Gerçek Postgres (pgvector) üzerinde migration testleri. CI'da `DATABASE_URL` ile çalışır."""

import os
from collections.abc import Iterator

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import Engine, inspect, text

from app.config import SERVICE_DIR
from app.db import get_engine
from app.models import KB_SCHEMA, Base

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="DATABASE_URL tanımlı değil"),
]


@pytest.fixture(scope="module")
def alembic_config() -> Config:
    return Config(str(SERVICE_DIR / "alembic.ini"))


@pytest.fixture(scope="module")
def engine(alembic_config: Config) -> Iterator[Engine]:
    command.upgrade(alembic_config, "head")
    yield get_engine()


def test_creates_kb_tables(engine: Engine) -> None:
    tables = set(inspect(engine).get_table_names(schema=KB_SCHEMA))
    assert {"sources", "chunks", "ingestion_logs", "alembic_version"} <= tables


def test_models_match_migrations(engine: Engine) -> None:
    def include_name(name, type_, parent_names):
        return name == KB_SCHEMA if type_ == "schema" else True

    with engine.connect() as conn:
        ctx = MigrationContext.configure(
            conn,
            opts={
                "include_schemas": True,
                "include_name": include_name,
                "version_table_schema": KB_SCHEMA,
            },
        )
        diff = compare_metadata(ctx, Base.metadata)
    assert diff == [], f"Modeller ile migration'lar arasında fark var: {diff}"


def test_hybrid_search_columns_work(engine: Engine) -> None:
    vector = "[" + ",".join(["0.1"] * 1024) + "]"
    with engine.begin() as conn:
        source_id = conn.execute(
            text(
                "INSERT INTO kb.sources (url, institution, title, process_codes) "
                "VALUES ('https://example.gov.tr/test', 'Test', 'Test', ARRAY['pasaport']) "
                "RETURNING id"
            )
        ).scalar_one()
        conn.execute(
            text(
                "INSERT INTO kb.chunks (source_id, ordinal, heading_path, content, embedding) "
                "VALUES (:sid, 0, 'Pasaport > Gerekli Belgeler', "
                "'Başvuru için kimlik kartı ve biyometrik fotoğraf gereklidir.', "
                "CAST(:vec AS vector))"
            ),
            {"sid": source_id, "vec": vector},
        )

        keyword_hit = conn.execute(
            text(
                "SELECT count(*) FROM kb.chunks "
                "WHERE tsv @@ plainto_tsquery('turkish', 'fotoğraflar')"
            )
        ).scalar_one()
        distance = conn.execute(
            text("SELECT embedding <=> CAST(:vec AS vector) FROM kb.chunks WHERE source_id = :sid"),
            {"sid": source_id, "vec": vector},
        ).scalar_one()

        conn.execute(text("DELETE FROM kb.sources WHERE id = :sid"), {"sid": source_id})

    assert keyword_hit == 1, "Türkçe kök bulma ('fotoğraflar' -> 'fotoğraf') çalışmalı"
    assert distance == pytest.approx(0.0, abs=1e-6)


def test_downgrade_and_upgrade_again(alembic_config: Config, engine: Engine) -> None:
    command.downgrade(alembic_config, "base")
    assert "sources" not in inspect(engine).get_table_names(schema=KB_SCHEMA)
    command.upgrade(alembic_config, "head")
    assert "sources" in inspect(engine).get_table_names(schema=KB_SCHEMA)

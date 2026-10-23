"""kb şeması: kaynaklar, parçalar ve indeksleme kayıtları

Revision ID: 0001
Revises:
Create Date: 2026-10-23
"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "kb"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "sources",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False, unique=True),
        sa.Column("institution", sa.String(200), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64)),
        sa.Column(
            "process_codes",
            postgresql.ARRAY(sa.String(64)),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_fetched_at", sa.DateTime(timezone=True)),
        sa.Column("last_changed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_sources_process_codes",
        "sources",
        ["process_codes"],
        schema=SCHEMA,
        postgresql_using="gin",
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey(f"{SCHEMA}.sources.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading_path", sa.Text()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1024)),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('turkish'::regconfig, coalesce(heading_path, '') || ' ' || content)",
                persisted=True,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("source_id", "ordinal", name="uq_chunks_source_ordinal"),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        schema=SCHEMA,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], schema=SCHEMA, postgresql_using="gin")

    op.create_table(
        "ingestion_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "source_id",
            sa.BigInteger(),
            sa.ForeignKey(f"{SCHEMA}.sources.id", ondelete="SET NULL"),
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("old_hash", sa.String(64)),
        sa.Column("new_hash", sa.String(64)),
        sa.Column("http_status", sa.Integer()),
        sa.Column("message", sa.Text()),
        sa.Column(
            "started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        schema=SCHEMA,
    )
    op.create_index("ix_ingestion_logs_started_at", "ingestion_logs", ["started_at"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("ingestion_logs", schema=SCHEMA)
    op.drop_table("chunks", schema=SCHEMA)
    op.drop_table("sources", schema=SCHEMA)
    # `vector` eklentisi bilerek kaldırılmaz: veritabanındaki başka nesneler kullanıyor olabilir.

"""kaynak ayıklama seçenekleri ve indeksleme kaydı indeksi

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "kb"


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column(
            "options",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        schema=SCHEMA,
    )
    op.create_index(
        "ix_ingestion_logs_source_started",
        "ingestion_logs",
        ["source_id", "started_at"],
        schema=SCHEMA,
    )


def downgrade() -> None:
    op.drop_index("ix_ingestion_logs_source_started", "ingestion_logs", schema=SCHEMA)
    op.drop_column("sources", "options", schema=SCHEMA)

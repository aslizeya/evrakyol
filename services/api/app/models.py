"""Bilgi tabanı (`kb` şeması) modelleri.

Bu tablolar yalnızca bu servis tarafından (Alembic ile) yönetilir.
Kullanıcıya ait tablolar `app` şemasındadır ve web uygulamasındaki Prisma tarafından yönetilir.
"""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

KB_SCHEMA = "kb"
# bge-m3 1024 boyutlu vektör üretir. Model değişirse yeni bir migration gerekir.
EMBEDDING_DIM = 1024


class Base(DeclarativeBase):
    metadata = MetaData(schema=KB_SCHEMA)


class Source(Base):
    """İzin listesindeki resmi bir alan adından çekilen tek bir sayfa veya belge."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    url: Mapped[str] = mapped_column(Text, unique=True)
    institution: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(Text)
    # Temizlenmiş ana içeriğin SHA-256 özeti (menü, tarih gibi değişken kısımlar hariç)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    # Bu kaynağın ilgili olduğu işlem kodları (config/process_types.json)
    process_codes: Mapped[list[str]] = mapped_column(ARRAY(String(64)), server_default=text("'{}'"))
    active: Mapped[bool] = mapped_column(server_default=text("true"))
    last_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    chunks: Mapped[list["Chunk"]] = relationship(
        back_populates="source", cascade="all, delete-orphan", order_by="Chunk.ordinal"
    )

    __table_args__ = (Index("ix_sources_process_codes", "process_codes", postgresql_using="gin"),)


class Chunk(Base):
    """Bir kaynağın başlık yapısı korunarak bölünmüş parçası."""

    __tablename__ = "chunks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"))
    ordinal: Mapped[int]
    # Parçanın içinde bulunduğu başlık hiyerarşisi, ör. "Araç Tescili > Gerekli Belgeler"
    heading_path: Mapped[str | None] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    # Anahtar kelime araması için Türkçe tam metin indeksi (hibrit aramanın ikinci ayağı)
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('turkish'::regconfig, coalesce(heading_path, '') || ' ' || content)",
            persisted=True,
        ),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[Source] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("source_id", "ordinal", name="uq_chunks_source_ordinal"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )


class IngestionLog(Base):
    """Her kaynak taramasının sonucu. Değişiklik geçmişi ve yönetici paneli için tutulur."""

    __tablename__ = "ingestion_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    url: Mapped[str] = mapped_column(Text)
    # new | unchanged | changed | failed | skipped_robots
    status: Mapped[str] = mapped_column(String(32))
    old_hash: Mapped[str | None] = mapped_column(String(64))
    new_hash: Mapped[str | None] = mapped_column(String(64))
    http_status: Mapped[int | None]
    message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_ingestion_logs_started_at", "started_at"),)

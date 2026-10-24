"""Kaynakları çekip ayıklayan, bölen, embedding üreten ve `kb` şemasına yazan hat."""

import difflib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import delete, select
from sqlalchemy.orm import Session, sessionmaker

from app.embedding import Embedder
from app.ingest.chunker import DEFAULT_MAX_CHARS, chunk_document
from app.ingest.extract import ExtractionError, extract
from app.ingest.fetcher import FetchError, NotAllowedError, PoliteFetcher, RobotsDisallowedError
from app.ingest.sources_config import SourceOptions, SourcesConfig
from app.models import Chunk, IngestionLog, Source
from app.text import turkish_lower

logger = logging.getLogger(__name__)

# Bu uzunluktan kısa içerik (ör. sadece menü kalmış sayfa) kaynak olarak kabul edilmez.
MIN_CONTENT_CHARS = 200


class IngestStatus(StrEnum):
    NEW = "new"
    CHANGED = "changed"
    UNCHANGED = "unchanged"
    REINDEXED = "reindexed"  # içerik aynı ama elle yeniden indekslendi
    FAILED = "failed"
    SKIPPED_ROBOTS = "skipped_robots"
    NOT_ALLOWED = "not_allowed"
    REJECTED = "rejected_content"


@dataclass(frozen=True)
class IngestResult:
    source_id: int
    url: str
    status: IngestStatus
    chunks: int = 0
    message: str | None = None


def _now() -> datetime:
    return datetime.now(UTC)


def _change_summary(old: str, new: str) -> str:
    old_lines, new_lines = old.splitlines(), new.splitlines()
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    added = removed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("replace", "delete"):
            removed += i2 - i1
        if tag in ("replace", "insert"):
            added += j2 - j1
    return f"benzerlik %{matcher.ratio() * 100:.0f}; +{added} / -{removed} satır"


class IngestionPipeline:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        fetcher: PoliteFetcher,
        embedder: Embedder,
        config: SourcesConfig,
        *,
        max_chars: int = DEFAULT_MAX_CHARS,
    ):
        self.session_factory = session_factory
        self.fetcher = fetcher
        self.embedder = embedder
        self.config = config
        self.max_chars = max_chars

    # --- yapılandırma -> veritabanı ---

    def sync_sources(self) -> tuple[int, int]:
        """config/sources.yaml'daki kaynakları veritabanına ekler veya günceller.

        `active` alanına dokunulmaz: yönetici panelinden devre dışı bırakılan kaynak öyle kalır.
        """
        created = updated = 0
        with self.session_factory() as session:
            for seed in self.config.sources:
                if not self.config.is_allowed(seed.url):
                    raise ValueError(f"Kaynak izin listesinde değil: {seed.url}")
                source = session.scalar(select(Source).where(Source.url == seed.url))
                values = {
                    "institution": seed.institution,
                    "title": seed.title or seed.url,
                    "process_codes": seed.process_codes,
                    "options": seed.options.model_dump(exclude_defaults=True),
                }
                if source is None:
                    session.add(Source(url=seed.url, **values))
                    created += 1
                else:
                    for key, value in values.items():
                        setattr(source, key, value)
                    updated += 1
            session.commit()
        return created, updated

    # --- indeksleme ---

    def run(
        self,
        *,
        source_ids: list[int] | None = None,
        process_code: str | None = None,
        force: bool = False,
    ) -> list[IngestResult]:
        with self.session_factory() as session:
            query = select(Source.id).order_by(Source.id)
            if source_ids:
                query = query.where(Source.id.in_(source_ids))
            else:
                query = query.where(Source.active.is_(True))
            if process_code:
                query = query.where(Source.process_codes.any(process_code))
            ids = list(session.scalars(query))
        return [self.index_source(source_id, force=force) for source_id in ids]

    def index_source(self, source_id: int, *, force: bool = False) -> IngestResult:
        started_at = _now()
        with self.session_factory() as session:
            source = session.get(Source, source_id)
            if source is None:
                raise ValueError(f"Kaynak bulunamadı: {source_id}")
            previous_hash = source.content_hash
            try:
                result, http_status, new_hash = self._process(session, source, force=force)
            except Exception as exc:
                # Beklenmeyen hata: mevcut parçalar korunur, hata kaydedilir.
                session.rollback()
                logger.exception("Kaynak indekslenemedi: %s", source.url)
                result = IngestResult(
                    source.id, source.url, IngestStatus.FAILED, message=type(exc).__name__
                )
                http_status, new_hash = None, None
            session.add(
                IngestionLog(
                    source_id=source.id,
                    url=source.url,
                    status=result.status.value,
                    old_hash=previous_hash,
                    new_hash=new_hash,
                    http_status=http_status,
                    message=result.message,
                    started_at=started_at,
                    finished_at=_now(),
                )
            )
            session.commit()
        logger.info(
            "%s -> %s (%s parça) %s", result.url, result.status, result.chunks, result.message or ""
        )
        return result

    def _process(
        self, session: Session, source: Source, *, force: bool
    ) -> tuple[IngestResult, int | None, str | None]:
        options = SourceOptions.model_validate(source.options or {})

        try:
            fetched = self.fetcher.fetch(source.url)
        except NotAllowedError as exc:
            return (
                IngestResult(source.id, source.url, IngestStatus.NOT_ALLOWED, message=str(exc)),
                None,
                None,
            )
        except RobotsDisallowedError as exc:
            return (
                IngestResult(source.id, source.url, IngestStatus.SKIPPED_ROBOTS, message=str(exc)),
                None,
                None,
            )
        except FetchError as exc:
            return (
                IngestResult(source.id, source.url, IngestStatus.FAILED, message=str(exc)),
                exc.status_code,
                None,
            )

        try:
            document = extract(
                fetched.content,
                fetched.content_type,
                legislation=options.legislation,
                articles=options.articles,
                charset=fetched.charset,
            )
        except ExtractionError as exc:
            return (
                IngestResult(source.id, source.url, IngestStatus.FAILED, message=str(exc)),
                fetched.status_code,
                None,
            )

        text = document.plain_text()
        rejected = self._rejection_reason(text)
        if rejected:
            return (
                IngestResult(source.id, source.url, IngestStatus.REJECTED, message=rejected),
                fetched.status_code,
                None,
            )

        new_hash = document.content_hash()
        source.last_fetched_at = _now()
        existing = list(
            session.scalars(
                select(Chunk).where(Chunk.source_id == source.id).order_by(Chunk.ordinal)
            )
        )
        if new_hash == source.content_hash and existing and not force:
            session.commit()
            return (
                IngestResult(source.id, source.url, IngestStatus.UNCHANGED, chunks=len(existing)),
                fetched.status_code,
                new_hash,
            )

        drafts = chunk_document(document, max_chars=self.max_chars)
        title = source.title or document.title or source.url
        vectors = self.embedder.embed_documents([d.embedding_text(title) for d in drafts])

        if new_hash == source.content_hash:
            status, message = IngestStatus.REINDEXED, None
        elif source.content_hash is None:
            status, message = IngestStatus.NEW, None
        else:
            status = IngestStatus.CHANGED
            message = _change_summary(
                "\n".join(c.content for c in existing), "\n".join(d.content for d in drafts)
            )
            source.last_changed_at = _now()

        session.execute(delete(Chunk).where(Chunk.source_id == source.id))
        session.add_all(
            Chunk(
                source_id=source.id,
                ordinal=d.ordinal,
                heading_path=d.heading_path,
                content=d.content,
                embedding=vector,
            )
            for d, vector in zip(drafts, vectors, strict=True)
        )
        if source.last_changed_at is None:
            source.last_changed_at = _now()
        source.content_hash = new_hash
        if not source.title or source.title == source.url:
            source.title = document.title or source.url
        session.commit()
        return (
            IngestResult(source.id, source.url, status, chunks=len(drafts), message=message),
            fetched.status_code,
            new_hash,
        )

    def _rejection_reason(self, text: str) -> str | None:
        folded = turkish_lower(text)
        for pattern in self.config.reject_patterns:
            if turkish_lower(pattern) in folded:
                return f"reddedilen içerik kalıbı: {pattern!r}"
        if len(text) < MIN_CONTENT_CHARS:
            return f"içerik çok kısa ({len(text)} karakter)"
        return None

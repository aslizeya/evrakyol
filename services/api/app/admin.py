"""Yönetici paneli için kaynak yönetimi uç noktaları (web uygulaması üzerinden çağrılır)."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_session, get_sessionmaker
from app.embedding import get_embedder
from app.ingest.fetcher import PoliteFetcher
from app.ingest.pipeline import IngestionPipeline
from app.ingest.sources_config import SourceOptions, get_sources_config
from app.models import Chunk, IngestionLog, Source
from app.process_types import get_process_types
from app.security import require_internal_token

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_internal_token)])

SessionDep = Annotated[Session, Depends(get_session)]


def _validate_process_codes(codes: list[str]) -> list[str]:
    known = {p.code for p in get_process_types()}
    unknown = sorted(set(codes) - known)
    if unknown:
        raise ValueError(f"Bilinmeyen işlem kodları: {', '.join(unknown)}")
    return codes


class SourceCreate(BaseModel):
    url: str
    institution: str | None = None
    title: str = Field(min_length=1)
    process_codes: list[str] = Field(min_length=1)
    options: SourceOptions = SourceOptions()

    @field_validator("url")
    @classmethod
    def _allowed(cls, url: str) -> str:
        if not get_sources_config().is_allowed(url):
            raise ValueError(
                "Adres izin listesindeki resmi alan adlarından birine ait olmalı (HTTPS)"
            )
        return url

    @field_validator("process_codes")
    @classmethod
    def _codes(cls, value: list[str]) -> list[str]:
        return _validate_process_codes(value)


class SourceUpdate(BaseModel):
    active: bool | None = None
    title: str | None = Field(default=None, min_length=1)
    institution: str | None = Field(default=None, min_length=1)
    process_codes: list[str] | None = Field(default=None, min_length=1)
    options: SourceOptions | None = None

    @field_validator("process_codes")
    @classmethod
    def _codes(cls, value: list[str] | None) -> list[str] | None:
        return _validate_process_codes(value) if value is not None else None


class SourceOut(BaseModel):
    id: int
    url: str
    institution: str
    title: str
    process_codes: list[str]
    options: dict
    active: bool
    chunk_count: int
    last_fetched_at: datetime | None
    last_changed_at: datetime | None
    last_status: str | None
    last_message: str | None


class IngestionLogOut(BaseModel):
    id: int
    source_id: int | None
    url: str
    status: str
    http_status: int | None
    message: str | None
    started_at: datetime
    finished_at: datetime | None


def _source_out(session: Session, source: Source) -> SourceOut:
    chunk_count = session.scalar(select(func.count()).where(Chunk.source_id == source.id)) or 0
    last = session.scalar(
        select(IngestionLog)
        .where(IngestionLog.source_id == source.id)
        .order_by(IngestionLog.started_at.desc())
        .limit(1)
    )
    return SourceOut(
        id=source.id,
        url=source.url,
        institution=source.institution,
        title=source.title,
        process_codes=source.process_codes,
        options=source.options or {},
        active=source.active,
        chunk_count=chunk_count,
        last_fetched_at=source.last_fetched_at,
        last_changed_at=source.last_changed_at,
        last_status=last.status if last else None,
        last_message=last.message if last else None,
    )


def _get_or_404(session: Session, source_id: int) -> Source:
    source = session.get(Source, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kaynak bulunamadı")
    return source


@router.get("/sources", response_model=list[SourceOut])
def list_sources(session: SessionDep) -> list[SourceOut]:
    return [_source_out(session, s) for s in session.scalars(select(Source).order_by(Source.id))]


@router.post("/sources", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
def create_source(body: SourceCreate, session: SessionDep) -> SourceOut:
    if session.scalar(select(Source.id).where(Source.url == body.url)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bu adres zaten kayıtlı")
    source = Source(
        url=body.url,
        institution=body.institution or get_sources_config().institution_for(body.url) or "",
        title=body.title,
        process_codes=body.process_codes,
        options=body.options.model_dump(exclude_defaults=True),
    )
    session.add(source)
    session.commit()
    return _source_out(session, source)


@router.patch("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: int, body: SourceUpdate, session: SessionDep) -> SourceOut:
    source = _get_or_404(session, source_id)
    changes = body.model_dump(exclude_unset=True)
    if "options" in changes and body.options is not None:
        changes["options"] = body.options.model_dump(exclude_defaults=True)
    for key, value in changes.items():
        setattr(source, key, value)
    session.commit()
    return _source_out(session, source)


def _reindex(source_id: int, force: bool) -> None:
    config = get_sources_config()
    pipeline = IngestionPipeline(get_sessionmaker(), PoliteFetcher(config), get_embedder(), config)
    pipeline.index_source(source_id, force=force)


@router.post("/sources/{source_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
def reindex_source(
    source_id: int,
    background: BackgroundTasks,
    session: SessionDep,
    force: bool = True,
) -> dict[str, str]:
    _get_or_404(session, source_id)
    background.add_task(_reindex, source_id, force)
    return {"status": "queued"}


@router.get("/ingestion-logs", response_model=list[IngestionLogOut])
def list_logs(
    session: SessionDep,
    source_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[IngestionLogOut]:
    query = select(IngestionLog).order_by(IngestionLog.started_at.desc()).limit(limit)
    if source_id is not None:
        query = query.where(IngestionLog.source_id == source_id)
    return [
        IngestionLogOut.model_validate(log, from_attributes=True) for log in session.scalars(query)
    ]

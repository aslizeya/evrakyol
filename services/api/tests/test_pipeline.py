"""İndeksleme hattının uçtan uca testleri (gerçek Postgres + sahte HTTP + sahte embedding)."""

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.embedding import FakeEmbedder
from app.ingest.fetcher import PoliteFetcher
from app.ingest.pipeline import IngestionPipeline, IngestStatus
from app.ingest.sources_config import SourcesConfig, SourceSeed
from app.models import Chunk, IngestionLog, Source

pytestmark = pytest.mark.db

URL = "https://example.gov.tr/mirascilik"
PARAGRAPH = (
    "Mirasçılık belgesi noterden veya sulh hukuk mahkemesinden alınabilir. "
    "Başvuru için kimlik belgesi ve miras bırakanın kimlik numarası yeterlidir. "
)


def page(items: list[str]) -> bytes:
    lis = "".join(f"<li>{i}</li>" for i in items)
    return (
        "<html><head><title>Mirasçılık</title></head><body><main>"
        f"<h1>Mirasçılık Belgesi</h1><p>{PARAGRAPH * 3}</p>"
        f"<h2>Gerekli belgeler</h2><ul>{lis}</ul></main></body></html>"
    ).encode()


class FakeSite:
    def __init__(self) -> None:
        self.body = page(["Kimlik belgesi", "Başvuru formu"])
        self.status = 200
        self.robots = "User-agent: *\nAllow: /\n"

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text=self.robots)
        if self.status != 200:
            return httpx.Response(self.status)
        return httpx.Response(200, content=self.body, headers={"content-type": "text/html"})


@pytest.fixture
def site() -> FakeSite:
    return FakeSite()


@pytest.fixture
def pipeline(
    db_sessionmaker: sessionmaker[Session], sources_config: SourcesConfig, site: FakeSite
) -> IngestionPipeline:
    config = sources_config.model_copy(
        update={
            "sources": [
                SourceSeed(
                    url=URL,
                    institution="Örnek Kurum",
                    title="Mirasçılık Belgesi",
                    process_codes=["mirascilik_belgesi"],
                )
            ]
        }
    )

    def make_fetcher() -> PoliteFetcher:
        return PoliteFetcher(
            config,
            httpx.Client(transport=httpx.MockTransport(site)),
            sleep=lambda _: None,
            max_retries=0,
        )

    p = IngestionPipeline(db_sessionmaker, make_fetcher(), FakeEmbedder(), config)
    p.make_fetcher = make_fetcher  # type: ignore[attr-defined]
    p.sync_sources()
    return p


def _source(pipeline: IngestionPipeline) -> Source:
    with pipeline.session_factory() as s:
        return s.scalars(select(Source)).one()


def _chunks(pipeline: IngestionPipeline) -> list[Chunk]:
    with pipeline.session_factory() as s:
        return list(s.scalars(select(Chunk).order_by(Chunk.ordinal)))


def _logs(pipeline: IngestionPipeline) -> list[IngestionLog]:
    with pipeline.session_factory() as s:
        return list(s.scalars(select(IngestionLog).order_by(IngestionLog.id)))


def test_sync_is_idempotent_and_keeps_admin_deactivation(pipeline: IngestionPipeline) -> None:
    with pipeline.session_factory() as s:
        s.scalars(select(Source)).one().active = False
        s.commit()
    assert pipeline.sync_sources() == (0, 1)
    assert _source(pipeline).active is False


def test_first_run_indexes_chunks_with_embeddings(pipeline: IngestionPipeline) -> None:
    [result] = pipeline.run()
    assert result.status == IngestStatus.NEW
    chunks = _chunks(pipeline)
    assert len(chunks) == result.chunks >= 2
    assert chunks[-1].heading_path == "Mirasçılık Belgesi > Gerekli belgeler"
    assert all(c.embedding is not None and len(c.embedding) == 1024 for c in chunks)
    source = _source(pipeline)
    assert source.content_hash and source.last_fetched_at and source.last_changed_at


def test_unchanged_content_is_not_reembedded(pipeline: IngestionPipeline) -> None:
    pipeline.run()
    first_ids = [c.id for c in _chunks(pipeline)]
    [result] = pipeline.run()
    assert result.status == IngestStatus.UNCHANGED
    assert [c.id for c in _chunks(pipeline)] == first_ids


def test_changed_content_replaces_chunks_and_logs_diff(
    pipeline: IngestionPipeline, site: FakeSite
) -> None:
    pipeline.run()
    old_hash = _source(pipeline).content_hash
    site.body = page(["Kimlik belgesi", "Başvuru formu", "Vekâletname (temsilen başvuruda)"])

    [result] = pipeline.run()

    assert result.status == IngestStatus.CHANGED
    assert "Vekâletname" in _chunks(pipeline)[-1].content
    log = _logs(pipeline)[-1]
    assert log.status == "changed"
    assert log.old_hash == old_hash and log.new_hash == _source(pipeline).content_hash
    assert "benzerlik" in (log.message or "")


def test_force_reindexes_identical_content(pipeline: IngestionPipeline) -> None:
    pipeline.run()
    [result] = pipeline.run(force=True)
    assert result.status == IngestStatus.REINDEXED


def test_fetch_failure_keeps_existing_chunks(pipeline: IngestionPipeline, site: FakeSite) -> None:
    pipeline.run()
    before = len(_chunks(pipeline))
    site.status = 500
    pipeline.fetcher = pipeline.make_fetcher()  # type: ignore[attr-defined]

    [result] = pipeline.run()

    assert result.status == IngestStatus.FAILED
    assert len(_chunks(pipeline)) == before
    assert _logs(pipeline)[-1].http_status == 500


def test_robots_disallow_is_logged_and_skipped(pipeline: IngestionPipeline, site: FakeSite) -> None:
    site.robots = "User-agent: *\nDisallow: /\n"
    [result] = pipeline.run()
    assert result.status == IngestStatus.SKIPPED_ROBOTS
    assert _chunks(pipeline) == []


def test_login_wall_is_rejected(pipeline: IngestionPipeline, site: FakeSite) -> None:
    site.body = (
        "<html><body><main><h2>Veraset İlamı Sorgulama</h2><p>Henüz kimliğinizi doğrulamadınız..."
        f"</p><p>{PARAGRAPH * 3}</p></main></body></html>"
    ).encode()
    [result] = pipeline.run()
    assert result.status == IngestStatus.REJECTED
    assert _chunks(pipeline) == []


def test_run_filters_by_process_code(pipeline: IngestionPipeline) -> None:
    assert pipeline.run(process_code="pasaport") == []
    assert len(pipeline.run(process_code="mirascilik_belgesi")) == 1


def test_keyword_and_vector_search_find_indexed_chunk(pipeline: IngestionPipeline) -> None:
    from sqlalchemy import text

    pipeline.run()
    with pipeline.session_factory() as s:
        hits = s.execute(
            text(
                "SELECT heading_path FROM kb.chunks "
                "WHERE tsv @@ plainto_tsquery('turkish', 'başvuru formları')"
            )
        ).all()
        target = _chunks(pipeline)[0]
        nearest = s.scalar(
            select(Chunk.id).order_by(Chunk.embedding.cosine_distance(target.embedding)).limit(1)
        )
    assert hits
    assert nearest == target.id

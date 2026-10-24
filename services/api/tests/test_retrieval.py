"""Hibrit arama (gerçek Postgres + sahte embedding)."""

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.embedding import FakeEmbedder
from app.models import Chunk, Source
from app.rag.retrieval import HybridRetriever

pytestmark = pytest.mark.db


@pytest.fixture
def retriever(db_sessionmaker: sessionmaker[Session]) -> HybridRetriever:
    embedder = FakeEmbedder()
    rows = [
        ("https://a.gov.tr/1", ["mirascilik_belgesi"], True,
         "Mirasçılık belgesi için kimlik belgesi ile noterliğe başvurulur."),
        ("https://a.gov.tr/2", ["mirascilik_belgesi"], True,
         "Sulh hukuk mahkemesinden veraset ilamı alınabilir."),
        ("https://a.gov.tr/3", ["pasaport"], True,
         "Pasaport başvurusu için biyometrik fotoğraf gerekir; noterlik ile ilgisi yoktur."),
        ("https://a.gov.tr/4", ["mirascilik_belgesi"], False,
         "Pasif kaynak: noterliğe başvuru eski usul."),
    ]  # fmt: skip
    with db_sessionmaker() as session:
        for url, codes, active, content in rows:
            source = Source(url=url, institution="Kurum", title=url, process_codes=codes)
            source.active = active
            source.chunks = [
                Chunk(ordinal=0, content=content, embedding=embedder.embed_documents([content])[0])
            ]
            session.add(source)
        session.commit()
    return HybridRetriever(db_sessionmaker, embedder)


def test_filters_by_process_and_active_sources(retriever: HybridRetriever) -> None:
    results = retriever.search("noterliğe başvuru", "mirascilik_belgesi")
    urls = {r.url for r in results}
    assert urls <= {"https://a.gov.tr/1", "https://a.gov.tr/2"}
    assert "https://a.gov.tr/3" not in urls  # başka işlem
    assert "https://a.gov.tr/4" not in urls  # pasif kaynak


def test_keyword_match_ranks_first_with_or_semantics(retriever: HybridRetriever) -> None:
    # Uzun doğal dil sorusu: tüm kelimeler hiçbir parçada birlikte geçmiyor (VE araması boş döner)
    results = retriever.search(
        "Babam vefat etti, mirasçılık belgesini noterliğe başvurarak almak istiyorum",
        "mirascilik_belgesi",
    )
    assert results[0].url == "https://a.gov.tr/1"
    assert results[0].source_title == "https://a.gov.tr/1"


def test_exact_vector_match_found(retriever: HybridRetriever) -> None:
    content = "Sulh hukuk mahkemesinden veraset ilamı alınabilir."
    results = retriever.search(content, "mirascilik_belgesi", limit=1)
    assert results[0].url == "https://a.gov.tr/2"


def test_no_sources_for_process(retriever: HybridRetriever) -> None:
    assert retriever.search("ehliyet", "ehliyet_yenileme") == []

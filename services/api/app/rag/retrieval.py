"""Hibrit arama: vektör (pgvector, kosinüs) + Türkçe tam metin, Reciprocal Rank Fusion ile."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

from app.embedding import Embedder
from app.models import Chunk, Source

RRF_K = 60  # Reciprocal Rank Fusion sabiti (yaygın varsayılan)


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: int
    source_id: int
    source_title: str
    url: str
    institution: str
    heading_path: str | None
    content: str
    last_fetched_at: datetime | None
    score: float


class Retriever(Protocol):
    def search(self, query: str, process_code: str, limit: int = 10) -> list[RetrievedChunk]: ...


# Kullanıcı cümlesindeki kelimeler "VE" yerine "VEYA" ile aranır; aksi halde uzun doğal dil
# soruları neredeyse hiçbir parçayla eşleşmez. Sıralamayı ts_rank_cd yapar.
_KEYWORD_SQL = text(
    """
    WITH q AS (
        SELECT NULLIF(replace(plainto_tsquery('turkish', :query)::text, '&', '|'), '')::tsquery
            AS query
    )
    SELECT c.id
    FROM kb.chunks c
    JOIN kb.sources s ON s.id = c.source_id, q
    WHERE s.active AND :code = ANY(s.process_codes) AND q.query IS NOT NULL AND c.tsv @@ q.query
    ORDER BY ts_rank_cd(c.tsv, q.query) DESC, c.id
    LIMIT :limit
    """
)


class HybridRetriever:
    def __init__(
        self, session_factory: sessionmaker[Session], embedder: Embedder, candidates: int = 30
    ):
        self.session_factory = session_factory
        self.embedder = embedder
        self.candidates = candidates

    def search(self, query: str, process_code: str, limit: int = 10) -> list[RetrievedChunk]:
        vector = self.embedder.embed_query(query)
        with self.session_factory() as session:
            vector_ids = list(
                session.scalars(
                    select(Chunk.id)
                    .join(Source, Source.id == Chunk.source_id)
                    .where(
                        Source.active.is_(True),
                        Source.process_codes.any(process_code),
                        Chunk.embedding.is_not(None),
                    )
                    .order_by(Chunk.embedding.cosine_distance(vector), Chunk.id)
                    .limit(self.candidates)
                )
            )
            keyword_ids = list(
                session.scalars(
                    _KEYWORD_SQL,
                    {"query": query, "code": process_code, "limit": self.candidates},
                )
            )
            scores = fuse_rankings([vector_ids, keyword_ids])
            top = sorted(scores, key=lambda cid: (-scores[cid], cid))[:limit]
            if not top:
                return []
            rows = session.execute(
                select(Chunk, Source).join(Source).where(Chunk.id.in_(top))
            ).all()
        by_id = {chunk.id: (chunk, source) for chunk, source in rows}
        return [
            RetrievedChunk(
                chunk_id=cid,
                source_id=by_id[cid][1].id,
                source_title=by_id[cid][1].title,
                url=by_id[cid][1].url,
                institution=by_id[cid][1].institution,
                heading_path=by_id[cid][0].heading_path,
                content=by_id[cid][0].content,
                last_fetched_at=by_id[cid][1].last_fetched_at,
                score=scores[cid],
            )
            for cid in top
            if cid in by_id
        ]


def fuse_rankings(rankings: list[list[int]], k: int = RRF_K) -> dict[int, float]:
    """Reciprocal Rank Fusion: her listede üst sıralarda olan parça daha yüksek puan alır."""
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, item in enumerate(ranking, start=1):
            scores[item] = scores.get(item, 0.0) + 1.0 / (k + rank)
    return scores

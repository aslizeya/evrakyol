"""Veritabanı olmadan arama (yalnızca deneme ve yerel değerlendirme içindir).

Kaynaklar config/sources.yaml'dan canlı çekilir ve kelime kökü örtüşmesiyle sıralanır.
Yayında `HybridRetriever` (pgvector + Türkçe tam metin) kullanılır.
"""

import re
import sys
import threading
from datetime import UTC, datetime

from app.ingest.chunker import chunk_document
from app.ingest.extract import ExtractionError, extract
from app.ingest.fetcher import FetchError, PoliteFetcher
from app.ingest.sources_config import SourceSeed, get_sources_config
from app.rag.retrieval import RetrievedChunk
from app.text import turkish_lower


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"\w+", turkish_lower(text)) if len(w) > 2}


class InMemoryRetriever:
    """Yalnızca deneme içindir: canlı çekilen parçaları kelime kökü örtüşmesiyle sıralar."""

    def __init__(self) -> None:
        self.config = get_sources_config()
        self.fetcher = PoliteFetcher(self.config, max_retries=0, timeout=30)
        self._cache: dict[str, list[RetrievedChunk]] = {}
        # Aynı kaynak birden çok işlemde kullanılır; adres başına bir kez indirilir.
        self._by_url: dict[str, list[RetrievedChunk]] = {}
        self._lock = threading.Lock()

    def warm_up(self) -> None:
        """Tüm kaynakları önceden çeker; ilk kullanıcı sorusu indirmeyi beklemez."""
        codes = sorted({code for seed in self.config.sources for code in seed.process_codes})
        for code in codes:
            self._chunks_for(code)
        print(f"Kaynaklar hazır: {len(self._by_url)} kaynak", file=sys.stderr)

    def search(self, query: str, process_code: str, limit: int = 10) -> list[RetrievedChunk]:
        chunks = self._chunks_for(process_code)
        wanted = _stems(query)
        scored = sorted(
            chunks,
            key=lambda c: -len(wanted & _stems(f"{c.heading_path} {c.content}")),
        )
        return scored[:limit]

    def _chunks_for(self, process_code: str) -> list[RetrievedChunk]:
        # Kaynaklar işlem başına bir kez çekilir (değerlendirmede vakalar aynı kaynakları kullanır).
        with self._lock:
            if process_code in self._cache:
                return self._cache[process_code]
            chunks = self._fetch(process_code)
            self._cache[process_code] = chunks
            return chunks

    def _fetch(self, process_code: str) -> list[RetrievedChunk]:
        chunks: list[RetrievedChunk] = []
        for i, seed in enumerate(self.config.sources, start=1):
            if process_code not in seed.process_codes:
                continue
            if seed.url not in self._by_url:
                self._by_url[seed.url] = self._fetch_source(i, seed)
            chunks.extend(self._by_url[seed.url])
        return chunks

    def _fetch_source(self, i: int, seed: SourceSeed) -> list[RetrievedChunk]:
        try:
            fetched = self.fetcher.fetch(seed.url)
            document = extract(
                fetched.content,
                fetched.content_type,
                legislation=seed.options.legislation,
                articles=seed.options.articles,
                charset=fetched.charset,
            )
        except (FetchError, ExtractionError) as exc:
            print(f"  (atlandı: {seed.title} — {exc})", file=sys.stderr)
            return []
        fetched_at = datetime.now(UTC)
        return [
            RetrievedChunk(
                chunk_id=i * 10_000 + draft.ordinal,
                source_id=i,
                source_title=seed.title or seed.url,
                url=seed.url,
                institution=seed.institution,
                heading_path=draft.heading_path,
                content=draft.content,
                last_fetched_at=fetched_at,
                score=0.0,
            )
            for draft in chunk_document(document)
        ]

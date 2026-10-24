"""Veritabanı olmadan uçtan uca deneme (gerçek LLM çağrısı yapar, ANTHROPIC_API_KEY gerekir).

    python -m app.rag demo "Babamdan kalan arabayı üzerime almak istiyorum"

Kaynaklar config/sources.yaml'dan canlı çekilir, bellekte basit kelime eşleşmesiyle aranır
(yayında pgvector + tam metin araması kullanılır). Netleştirici sorular komut satırında sorulur.
"""

import argparse
import json
import logging
import re
import sys

from app.ingest.chunker import chunk_document
from app.ingest.extract import ExtractionError, extract
from app.ingest.fetcher import FetchError, PoliteFetcher
from app.ingest.sources_config import get_sources_config
from app.llm import get_llm
from app.process_types import get_process_types
from app.rag.retrieval import RetrievedChunk
from app.rag.roadmap import RoadmapService
from app.rag.understanding import understand
from app.text import turkish_lower


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"\w+", turkish_lower(text)) if len(w) > 2}


class InMemoryRetriever:
    """Yalnızca deneme içindir: canlı çekilen parçaları kelime kökü örtüşmesiyle sıralar."""

    def __init__(self) -> None:
        self.config = get_sources_config()
        self.fetcher = PoliteFetcher(self.config, max_retries=0, timeout=30)

    def search(self, query: str, process_code: str, limit: int = 10) -> list[RetrievedChunk]:
        chunks: list[RetrievedChunk] = []
        for i, seed in enumerate(self.config.sources, start=1):
            if process_code not in seed.process_codes:
                continue
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
                continue
            for draft in chunk_document(document):
                chunks.append(
                    RetrievedChunk(
                        chunk_id=i * 10_000 + draft.ordinal,
                        source_id=i,
                        source_title=seed.title or seed.url,
                        url=seed.url,
                        institution=seed.institution,
                        heading_path=draft.heading_path,
                        content=draft.content,
                        last_fetched_at=None,
                        score=0.0,
                    )
                )
        wanted = _stems(query)
        scored = sorted(
            chunks,
            key=lambda c: -len(wanted & _stems(f"{c.heading_path} {c.content}")),
        )
        return scored[:limit]


def _ask(question) -> str:
    print(f"\n{question.question}")
    for n, option in enumerate(question.options, start=1):
        print(f"  {n}) {option}")
    while True:
        choice = input("Seçiminiz: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(question.options):
            return question.options[int(choice) - 1]


def demo(text: str) -> int:
    llm = get_llm()
    process_types = list(get_process_types())
    result = understand(text, llm=llm, process_types=process_types)
    if result.status == "out_of_scope" or result.process is None:
        print("Kapsam dışı bir işlem.")
        return 0
    print(f"İşlem: {result.process.name}")
    answers = dict(result.answers)
    for question in result.questions:
        answers[question.key] = _ask(question)

    print("\nKaynaklar çekiliyor ve yol haritası hazırlanıyor...", file=sys.stderr)
    outcome = RoadmapService(InMemoryRetriever(), llm).build(text, result.process, answers)
    if outcome.roadmap is None:
        print(f"Kaynak bulunamadı. Yönlendirme: {outcome.referral}")
    else:
        print(json.dumps(outcome.roadmap.model_dump(), ensure_ascii=False, indent=2))
    print(
        f"\n[doğrulanamayan adım: {outcome.dropped_steps}, "
        f"doğrulanamayan uyarı: {outcome.dropped_warnings}, model: {outcome.model}]",
        file=sys.stderr,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(prog="python -m app.rag")
    sub = parser.add_subparsers(dest="command", required=True)
    demo_parser = sub.add_parser("demo", help="veritabanı olmadan uçtan uca deneme")
    demo_parser.add_argument("text")
    args = parser.parse_args(argv)
    return demo(args.text)


if __name__ == "__main__":
    sys.exit(main())

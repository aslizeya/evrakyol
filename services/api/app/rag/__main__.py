"""Veritabanı olmadan uçtan uca deneme (gerçek LLM çağrısı yapar, ANTHROPIC_API_KEY gerekir).

    python -m app.rag demo "Babamdan kalan arabayı üzerime almak istiyorum"

Kaynaklar config/sources.yaml'dan canlı çekilir, bellekte basit kelime eşleşmesiyle aranır
(yayında pgvector + tam metin araması kullanılır). Netleştirici sorular komut satırında sorulur.
"""

import argparse
import json
import logging
import sys

from app.llm import get_llm
from app.process_types import get_process_types
from app.rag.memory_retriever import InMemoryRetriever
from app.rag.roadmap import RoadmapService
from app.rag.understanding import understand


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

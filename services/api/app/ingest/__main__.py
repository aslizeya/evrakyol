"""Veri toplama komut satırı aracı.

    python -m app.ingest sync                         # config/sources.yaml -> veritabanı
    python -m app.ingest run [--process KOD] [--source-id N ...] [--force]
    python -m app.ingest status                       # kaynakların son durumu
    python -m app.ingest preview URL [--legislation] [--articles 495-501 598]

`run` periyodik güncelleme için zamanlanmış görev (cron) olarak çalıştırılır: içeriği
değişmeyen kaynaklar yeniden embedding'lenmez, değişenler yeniden indekslenir ve loglanır.
"""

import argparse
import logging
import sys

from sqlalchemy import func, select

from app.config import get_settings
from app.ingest.chunker import chunk_document
from app.ingest.extract import extract
from app.ingest.fetcher import PoliteFetcher
from app.ingest.sources_config import get_sources_config


def _pipeline():
    from app.db import get_sessionmaker
    from app.embedding import get_embedder
    from app.ingest.pipeline import IngestionPipeline

    config = get_sources_config()
    return IngestionPipeline(get_sessionmaker(), PoliteFetcher(config), get_embedder(), config)


def cmd_sync(_: argparse.Namespace) -> int:
    created, updated = _pipeline().sync_sources()
    print(f"{created} kaynak eklendi, {updated} kaynak güncellendi.")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    results = _pipeline().run(
        source_ids=args.source_id, process_code=args.process, force=args.force
    )
    failed = 0
    for r in results:
        print(f"[{r.status.value:>16}] #{r.source_id} {r.url} ({r.chunks} parça) {r.message or ''}")
        failed += r.status.value == "failed"
    print(f"Toplam {len(results)} kaynak, {failed} hata.")
    return 1 if failed else 0


def cmd_status(_: argparse.Namespace) -> int:
    from app.db import get_sessionmaker
    from app.models import Chunk, IngestionLog, Source

    with get_sessionmaker()() as session:
        chunk_counts = dict(
            session.execute(select(Chunk.source_id, func.count()).group_by(Chunk.source_id)).all()
        )
        for source in session.scalars(select(Source).order_by(Source.id)):
            last = session.scalar(
                select(IngestionLog)
                .where(IngestionLog.source_id == source.id)
                .order_by(IngestionLog.started_at.desc())
                .limit(1)
            )
            status = (
                f"{last.status} ({last.started_at:%Y-%m-%d %H:%M})" if last else "hiç çalışmadı"
            )
            flag = "" if source.active else " [pasif]"
            print(
                f"#{source.id}{flag} {source.institution} | {source.title}\n"
                f"    {chunk_counts.get(source.id, 0)} parça | son durum: {status}"
            )
    return 0


def cmd_preview(args: argparse.Namespace) -> int:
    """Veritabanına yazmadan bir kaynağı çekip ayıklama ve bölme sonucunu gösterir."""
    fetcher = PoliteFetcher(get_sources_config())
    fetched = fetcher.fetch(args.url)
    document = extract(
        fetched.content,
        fetched.content_type,
        legislation=args.legislation,
        articles=args.articles,
        charset=fetched.charset,
    )
    chunks = chunk_document(document)
    print(f"Başlık: {document.title}\nTür: {fetched.content_type}\nParça sayısı: {len(chunks)}\n")
    for chunk in chunks[: args.max_chunks]:
        print(f"--- #{chunk.ordinal} [{chunk.heading_path or '-'}] ({len(chunk.content)} kr)")
        print(chunk.content[: args.max_chars])
        print()
    return 0


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=get_settings().log_level.upper(), format="%(levelname)s %(name)s: %(message)s"
    )
    parser = argparse.ArgumentParser(prog="python -m app.ingest", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("sync", help="config/sources.yaml'ı veritabanına aktar").set_defaults(
        func=cmd_sync
    )

    run = sub.add_parser("run", help="kaynakları çek ve indeksle")
    run.add_argument("--process", help="yalnızca bu işlem koduna ait kaynaklar")
    run.add_argument("--source-id", type=int, nargs="+", help="yalnızca bu kaynaklar")
    run.add_argument("--force", action="store_true", help="içerik değişmese de yeniden indeksle")
    run.set_defaults(func=cmd_run)

    sub.add_parser("status", help="kaynakların son durumu").set_defaults(func=cmd_status)

    preview = sub.add_parser("preview", help="veritabanına yazmadan ayıklama önizlemesi")
    preview.add_argument("url")
    preview.add_argument("--legislation", action="store_true")
    preview.add_argument("--articles", nargs="+")
    preview.add_argument("--max-chunks", type=int, default=10)
    preview.add_argument("--max-chars", type=int, default=600)
    preview.set_defaults(func=cmd_preview)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

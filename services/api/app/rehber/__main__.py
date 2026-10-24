"""Rehber içeriğinin kaynaklarla doğrulanması.

    python -m app.rehber kontrol

Her alıntı, kaynağın güncel metninde aranır ve sonuç config/rehber/dogrulama.json dosyasına
yazılır. Kaynağa ulaşılamazsa o kaynağın önceki sonuçları korunur (geçici erişim sorunu içeriği
gizlemesin). Bir alıntı bulunamazsa komut 1 ile çıkar: kaynak değişmiş olabilir, içerik gözden
geçirilmelidir.
"""

import argparse
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime

from app.ingest.sources_config import get_sources_config
from app.rag.memory_retriever import InMemoryRetriever
from app.rag.roadmap import quote_found
from app.rehber import (
    VERIFICATION_FILE,
    SourceCheck,
    Verification,
    get_guides,
    guides_dir,
    load_verification,
)


def check() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    sources = get_sources_config()
    guides = get_guides()
    previous = load_verification(guides_dir())
    result = Verification()
    today = datetime.now(UTC).date().isoformat()
    fetcher = InMemoryRetriever()
    failures: list[str] = []

    evidence_by_url: dict[str, list] = {}
    for guide in guides.values():
        for item in guide.evidence():
            evidence_by_url.setdefault(item.kaynak, []).append((guide.islem, item))

    for url, items in evidence_by_url.items():
        index, seed = next((i, s) for i, s in enumerate(sources.sources, 1) if s.url == url)
        chunks = fetcher._fetch_source(index, seed)
        title = seed.title or url
        if not chunks:
            print(f"! {title}: kaynağa ulaşılamadı, önceki sonuçlar korunuyor")
            result.kaynaklar[url] = previous.kaynaklar.get(url, SourceCheck()).model_copy(
                update={"durum": "erisilemedi"}
            )
            for _, item in items:
                result.alintilar[item.key] = previous.alintilar.get(item.key, False)
            continue
        whole = replace(
            chunks[0],
            heading_path="",
            content=" ".join(f"{c.heading_path or ''} {c.content}" for c in chunks),
        )
        result.kaynaklar[url] = SourceCheck(son_kontrol=today, durum="ok")
        found_count = 0
        for islem, item in items:
            found = any(quote_found(item.alinti, c) for c in chunks) or quote_found(
                item.alinti, whole
            )
            result.alintilar[item.key] = found
            if found:
                found_count += 1
            else:
                was = (
                    " (önceki kontrolde vardı: kaynak değişmiş olabilir)"
                    if previous.alintilar.get(item.key)
                    else ""
                )
                failures.append(f"{islem} · {title}: “{item.alinti[:80]}…”{was}")
        print(f"✓ {title}: {found_count}/{len(items)} alıntı bulundu")

    path = guides_dir() / VERIFICATION_FILE
    data = result.model_dump()
    data["kaynaklar"] = dict(sorted(data["kaynaklar"].items()))
    data["alintilar"] = dict(sorted(data["alintilar"].items()))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Sonuç yazıldı: {path}")
    if failures:
        print("\nBulunamayan alıntılar (bu alıntılara dayanan adımlar gösterilmeyecek):")
        for line in failures:
            print("  - " + line)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.rehber")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("kontrol", help="Alıntıları kaynakların güncel metninde doğrula")
    parser.parse_args(argv)
    return check()


if __name__ == "__main__":
    sys.exit(main())

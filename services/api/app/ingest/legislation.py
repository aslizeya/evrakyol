"""Kanun ve yönetmelik metinlerini maddelere bölme.

Mevzuat Bilgi Sistemi PDF'lerinde madde biçimi: "Madde 598 - ..." (eski), "MADDE 20 – ..." (yeni).
Maddenin kenar başlığı (ör. "B. Mirasçılık belgesi") madde satırından hemen önce gelir;
bu satırlar bir önceki maddeden alınıp ait olduğu maddenin başlığına taşınır.
"""

import re
from dataclasses import dataclass

ARTICLE_LINE = re.compile(
    r"^(?P<prefix>(?:ek|geçici|EK|GEÇİCİ|Ek|Geçici)\s+)?(?:MADDE|Madde)\s+"
    r"(?P<number>\d+)(?:\s*/\s*(?P<suffix>[A-ZÇĞİÖŞÜ]))?\s*[-–—]\s*(?P<rest>.*)$"
)
_SIDE_TITLE_MAX = 80
_MAX_SIDE_TITLE_LINES = 3


@dataclass
class Article:
    label: str  # "598", "71/B", "Geçici 1"
    number: int
    supplementary: bool  # ek veya geçici madde
    side_titles: list[str]
    lines: list[str]

    @property
    def heading(self) -> str:
        title = " / ".join(self.side_titles)
        return f"Madde {self.label} – {title}" if title else f"Madde {self.label}"


def parse_ranges(ranges: list[str]) -> list[tuple[int, int]]:
    result = []
    for item in ranges:
        start, _, end = item.partition("-")
        result.append((int(start), int(end or start)))
    return result


_KEY_VALUE = re.compile(r"\S\s*:\s+\S")  # "Kanun Numarası : 4721" gibi künye satırları


def _is_side_title(line: str) -> bool:
    return (
        len(line) <= _SIDE_TITLE_MAX
        and not line.endswith((".", ",", ";"))
        and not _KEY_VALUE.search(line)
    )


def split_articles(
    lines: list[str], articles: list[str] | None = None
) -> tuple[list[str], list[Article]]:
    """(önsöz, maddeler) döndürür. `articles` verilirse yalnızca o maddeler kalır."""
    preamble: list[str] = []
    parsed: list[Article] = []

    for line in lines:
        match = ARTICLE_LINE.match(line)
        if not match:
            (parsed[-1].lines if parsed else preamble).append(line)
            continue

        previous = parsed[-1].lines if parsed else preamble
        side_titles: list[str] = []
        while (
            previous
            and len(side_titles) < _MAX_SIDE_TITLE_LINES
            and _is_side_title(previous[-1])
            # Bir önceki maddenin tek satırını başlık diye çalmamak için en az bir satır bırak.
            and (len(previous) > 1 or not parsed)
        ):
            side_titles.insert(0, previous.pop())

        prefix = (match["prefix"] or "").strip().capitalize()
        number = int(match["number"])
        label = f"{number}/{match['suffix']}" if match["suffix"] else str(number)
        parsed.append(
            Article(
                label=f"{prefix} {label}" if prefix else label,
                number=number,
                supplementary=bool(prefix),
                side_titles=[t.rstrip(":").strip() for t in side_titles],
                lines=[match["rest"]] if match["rest"] else [],
            )
        )

    if articles:
        ranges = parse_ranges(articles)
        parsed = [
            a
            for a in parsed
            if not a.supplementary and any(lo <= a.number <= hi for lo, hi in ranges)
        ]
    return preamble, parsed

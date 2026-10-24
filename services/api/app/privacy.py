"""KVKK: kullanıcı metnindeki kişisel verilerin maskelenmesi.

Ürün bu verileri istemez; kullanıcı kendiliğinden yazarsa metin LLM'e gönderilmeden,
loglanmadan ve kaydedilmeden önce maskelenir. Yaklaşım temkinlidir: emin olunamayan
11 haneli sayılar da maskelenir (yanlış pozitif, sızıntıdan iyidir).
"""

import re
from collections import Counter
from dataclasses import dataclass, field

_LETTERS = "a-zA-ZçğıöşüÇĞİÖŞÜ"

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("IBAN", re.compile(r"\bTR\s?\d{2}(?:\s?\d{4}){5}\s?\d{2}\b", re.I)),
    ("E_POSTA", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    (
        "TELEFON",
        re.compile(r"(?<!\d)(?:\+90|0)\s*\(?\d{3}\)?[\s-]?\d{3}[\s-]?\d{2}[\s-]?\d{2}(?!\d)"),
    ),
    ("TC_KIMLIK", re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)")),
    (
        "PLAKA",
        re.compile(r"(?<![\w])(?:0[1-9]|[1-7]\d|8[01])\s?(?!TL\b)[A-Za-z]{1,3}\s?\d{2,5}(?![\w])"),
    ),
    (
        "ADRES",
        re.compile(
            rf"(?:[{_LETTERS}0-9.]+\s+){{1,3}}"
            r"(?:Mahallesi|Mah\.|Mh\.|Sokağı|Sokak|Sok\.|Sk\.|Caddesi|Cad\.|Cd\.|Bulvarı|Blv\.)"
            rf"|\b(?:No|Daire|Kat)\s*[:.]?\s*\d+[/{_LETTERS}0-9]*",
            re.I,
        ),
    ),
]


@dataclass(frozen=True)
class MaskResult:
    text: str
    found: dict[str, int] = field(default_factory=dict)

    @property
    def had_personal_data(self) -> bool:
        return bool(self.found)


def mask_pii(text: str) -> MaskResult:
    found: Counter[str] = Counter()
    for label, pattern in _PATTERNS:

        def replace(_: re.Match[str], label: str = label) -> str:
            found[label] += 1
            return f"[{label}]"

        text = pattern.sub(replace, text)
    # Art arda gelen aynı etiketleri birleştir: "[ADRES] [ADRES]" -> "[ADRES]"
    text = re.sub(r"(\[(\w+)\])(?:[\s,]*\[\2\])+", r"\1", text)
    return MaskResult(text=text, found=dict(found))

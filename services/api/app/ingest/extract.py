"""HTML ve PDF içeriğinden başlık yapısı korunarak metin ayıklama.

Resmi sitelerin çoğu başlıkları <h2> yerine kalın veya büyük harfli bir satırla yazar
(ör. EGM: "E- VERASET YOLUYLA İNTİKAL EDEN ARAÇLAR:"). Bu satırlar başlık olarak tanınır;
aksi halde altındaki evrak listesi bağlamından kopar.
"""

import hashlib
import io
import re
import unicodedata
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Literal

from lxml import html as lxml_html
from lxml.etree import ParserError, _Element
from pypdf import PdfReader

from app.ingest.legislation import split_articles


@dataclass(frozen=True)
class Block:
    kind: Literal["heading", "text"]
    text: str
    level: int = 0  # yalnızca başlıklar için: 1 (en üst) .. 6


@dataclass
class Document:
    title: str | None
    blocks: list[Block] = field(default_factory=list)

    def plain_text(self) -> str:
        return "\n".join(b.text for b in self.blocks)

    def content_hash(self) -> str:
        """Ayıklanmış içeriğin özeti; menü, çerez metni gibi değişken kısımlar zaten atılmıştır."""
        return hashlib.sha256(self.plain_text().encode("utf-8")).hexdigest()


class ExtractionError(Exception):
    pass


# --- metin yardımcıları ---

_INVISIBLE = dict.fromkeys(map(ord, "​‌‍﻿­"))
_NUMERIC_MARKER = re.compile(r"^\s*\d+\s*[-.)]\s")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text).translate(_INVISIBLE)
    return re.sub(r"\s+", " ", text).strip()


def _mostly_upper(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 4 and sum(c.isupper() for c in letters) / len(letters) >= 0.8


def _looks_like_heading(text: str, bold_ratio: float) -> bool:
    # Başlıklar cümle gibi noktayla bitmez ve madde işaretiyle başlamaz.
    if not 3 <= len(text) <= 150 or text.endswith((",", ";", ".")) or text[0] in "·•*-–▪●":
        return False
    if _NUMERIC_MARKER.match(text):  # "1- Nüfus cüzdanı," gibi liste maddeleri
        return False
    return bold_ratio >= 0.9 or (_mostly_upper(text) and len(text) <= 100)


# --- HTML ---

_DROP_TAGS = [
    "script",
    "style",
    "noscript",
    "template",
    "iframe",
    "svg",
    "nav",
    "header",
    "footer",
    "aside",
    "button",
    "select",
    "input",
    "textarea",
    "object",
    "embed",
]
_DROP_TOKENS = {
    "modal", "cookie", "cookies", "cerez", "çerez", "breadcrumb", "navbar", "nav", "menu",
    "sidebar", "footer", "share", "social", "skip", "popup", "banner",
}  # fmt: skip
_BLOCK_TAGS = set(
    [
        "p",
        "div",
        "section",
        "article",
        "main",
        "li",
        "ul",
        "ol",
        "td",
        "th",
        "tr",
        "table",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        "pre",
        "blockquote",
        "dd",
        "dt",
        "dl",
        "figure",
        "figcaption",
        "center",
    ]
)
_HEADING_TAGS = {f"h{i}": i for i in range(1, 7)}
_BOLD_STYLE = re.compile(r"font-weight\s*:\s*(bold|[6-9]00)", re.I)


def _is_boilerplate(el: _Element) -> bool:
    if el.tag in _DROP_TAGS:
        return True
    attrs = f"{el.get('class', '')} {el.get('id', '')}".lower()
    tokens = set(re.split(r"[\s_-]+", attrs))
    return bool(tokens & _DROP_TOKENS) or el.get("aria-hidden") == "true"


def _bold_ratio(el: _Element) -> float:
    total = len(normalize(el.text_content()))
    if not total:
        return 0.0
    bold_chars = 0
    counted: set[int] = set()
    for node in el.iter():
        if not isinstance(node.tag, str):
            continue
        is_bold = node.tag in ("b", "strong") or _BOLD_STYLE.search(node.get("style", ""))
        if is_bold and not any(id(a) in counted for a in node.iterancestors()):
            counted.add(id(node))
            bold_chars += len(normalize(node.text_content()))
    return bold_chars / total


def _link_ratio(el: _Element) -> float:
    total = len(normalize(el.text_content()))
    if not total:
        return 0.0
    links = sum(len(normalize(a.text_content())) for a in el.iter("a"))
    return links / total


_COOKIE_NOTICE = re.compile(r"çerez|cookie", re.I)


def _is_noise(el: _Element, text: str) -> bool:
    """Menü bağlantıları ve kısa çerez bildirimleri içerik sayılmaz."""
    if el.tag == "a" or _link_ratio(el) >= 0.7:
        return True
    return len(text) < 500 and bool(_COOKIE_NOTICE.search(text))


def _has_block_children(el: _Element) -> bool:
    # Satır içi bir etiket (<span>, <font>) blok elemanları sarmalayabilir; tüm alt ağaca bakılır.
    return any(isinstance(c.tag, str) and c.tag in _BLOCK_TAGS for c in el.iterdescendants())


def _walk(el: _Element) -> Iterator[Block]:
    tag = el.tag if isinstance(el.tag, str) else ""
    if tag in _HEADING_TAGS:
        text = normalize(el.text_content())
        if text:
            yield Block("heading", text, _HEADING_TAGS[tag])
        return
    if tag == "tr":
        cells = [normalize(c.text_content()) for c in el if c.tag in ("td", "th")]
        row = " | ".join(c for c in cells if c)
        if row:
            yield Block("text", row)
        return
    if not _has_block_children(el):
        text = normalize(el.text_content())
        if not text or _is_noise(el, text):
            return
        if _looks_like_heading(text, _bold_ratio(el)):
            yield Block("heading", text.rstrip(":").strip(), 4 if not _mostly_upper(text) else 3)
        else:
            yield Block("text", f"- {text}" if tag == "li" else text)
        return

    # Blok çocukları olan eleman: aradaki serbest metinler de korunur.
    if el.text and normalize(el.text):
        yield Block("text", normalize(el.text))
    for child in el:
        if isinstance(child.tag, str) and not _is_boilerplate(child):
            yield from _walk(child)
        if child.tail and normalize(child.tail):
            yield Block("text", normalize(child.tail))


def _main_container(doc: _Element) -> _Element:
    for xpath in ("//main", "//*[@role='main']", "//article"):
        for candidate in doc.xpath(xpath):
            if len(normalize(candidate.text_content())) >= 200:
                return candidate
    body = doc.find("body")
    return body if body is not None else doc


_META_CHARSET = re.compile(rb"""<meta[^>]+charset=["']?([\w-]+)""", re.I)
_XML_DECLARATION = re.compile(r"^\s*<\?xml[^>]*\?>")


def decode_html(content: bytes, charset: str | None = None) -> str:
    """Kodlama sırası: HTTP başlığı, <meta charset>, UTF-8, Windows-1254 (Türkçe)."""
    candidates = [charset]
    meta = _META_CHARSET.search(content[:4096])
    if meta:
        candidates.append(meta.group(1).decode("ascii", "ignore"))
    candidates += ["utf-8", "cp1254"]
    for encoding in filter(None, candidates):
        try:
            return content.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
    return content.decode("utf-8", errors="replace")


def extract_html(content: bytes, charset: str | None = None) -> Document:
    # lxml'e çözülmüş metin verilir; aksi halde kodlama belirtilmemiş sayfalar Latin-1 sanılır.
    text = _XML_DECLARATION.sub("", decode_html(content, charset))
    try:
        doc = lxml_html.document_fromstring(text)
    except (ParserError, ValueError) as exc:
        raise ExtractionError(f"HTML ayrıştırılamadı: {exc}") from exc

    title_el = doc.find(".//title")
    title = normalize(title_el.text_content()) if title_el is not None else None

    for el in list(doc.iter()):
        if isinstance(el.tag, str) and el.getparent() is not None and _is_boilerplate(el):
            el.drop_tree()

    blocks: list[Block] = []
    for block in _walk(_main_container(doc)):
        if not blocks or blocks[-1] != block:  # art arda tekrarları at
            blocks.append(block)
    return Document(title=title or None, blocks=blocks)


# --- PDF ---

_PAGE_NUMBER = re.compile(r"^(sayfa\s*)?\d+(\s*/\s*\d+)?$", re.I)
_PARAGRAPH_START = re.compile(r"^(\(\d+\)|[a-zçğıöşü]\)|[-•▪●]\s|\d+[.)-]\s)")


def _pdf_page_lines(content: bytes) -> list[list[str]]:
    try:
        reader = PdfReader(io.BytesIO(content))
        pages = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise ExtractionError(f"PDF okunamadı: {type(exc).__name__}") from exc
    return [[normalize(line) for line in page.splitlines() if normalize(line)] for page in pages]


def _drop_repeated_lines(pages: list[list[str]]) -> list[str]:
    """Sayfa numaralarını ve sayfaların yarısından fazlasında tekrar eden üst/alt bilgileri atar."""
    if len(pages) >= 3:
        counts = Counter(line for page in pages for line in set(page))
        repeated = {line for line, n in counts.items() if n > len(pages) / 2}
    else:
        repeated = set()
    return [
        line
        for page in pages
        for line in page
        if line not in repeated and not _PAGE_NUMBER.match(line)
    ]


def lines_to_blocks(lines: list[str], *, detect_headings: bool = True) -> list[Block]:
    """PDF satırlarını paragraflara birleştirir; kısa büyük harfli satırları başlık sayar."""
    blocks: list[Block] = []
    paragraph: list[str] = []

    def flush() -> None:
        if paragraph:
            blocks.append(Block("text", " ".join(paragraph)))
            paragraph.clear()

    for line in lines:
        if (
            detect_headings
            and _mostly_upper(line)
            and len(line) <= 90
            and not line.endswith((".", ",", ";"))
        ):
            flush()
            blocks.append(Block("heading", line.rstrip(":").strip(), 3))
            continue
        ends_sentence = bool(paragraph) and paragraph[-1].endswith((".", ":", "!", "?"))
        if paragraph and (_PARAGRAPH_START.match(line) or (ends_sentence and line[:1].isupper())):
            flush()
        paragraph.append(line)
    flush()
    return blocks


def extract_pdf(
    content: bytes, *, legislation: bool = False, articles: list[str] | None = None
) -> Document:
    lines = _drop_repeated_lines(_pdf_page_lines(content))
    if not lines:
        raise ExtractionError("PDF'te metin bulunamadı (taranmış görüntü olabilir)")
    if not legislation:
        return Document(title=None, blocks=lines_to_blocks(lines))

    preamble, parsed = split_articles(lines, articles)
    blocks: list[Block] = []
    if not articles:
        blocks.extend(lines_to_blocks(preamble, detect_headings=False))
    for article in parsed:
        blocks.append(Block("heading", article.heading, 2))
        blocks.extend(lines_to_blocks(article.lines, detect_headings=False))
    if not parsed:
        raise ExtractionError("Mevzuat metninde istenen maddeler bulunamadı")
    return Document(title=None, blocks=blocks)


def extract(
    content: bytes,
    content_type: str,
    *,
    legislation: bool = False,
    articles: list[str] | None = None,
    charset: str | None = None,
) -> Document:
    if content_type == "application/pdf":
        return extract_pdf(content, legislation=legislation, articles=articles)
    return extract_html(content, charset)

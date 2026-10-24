"""Ayıklanmış belgeyi başlık hiyerarşisini koruyarak parçalara bölme."""

import re
from dataclasses import dataclass

from app.ingest.extract import Document

DEFAULT_MAX_CHARS = 1500
_SENTENCE_END = re.compile(r"(?<=[.!?;:])\s+")


@dataclass(frozen=True)
class ChunkDraft:
    ordinal: int
    heading_path: str | None
    content: str

    def embedding_text(self, source_title: str) -> str:
        """Embedding'e verilen metin: kaynak başlığı ve başlık yolu, parçanın bağlamını taşır."""
        parts = [source_title, self.heading_path or "", self.content]
        return "\n".join(p for p in parts if p)


def _split_long(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    pieces: list[str] = []
    current = ""
    for sentence in _SENTENCE_END.split(text):
        while len(sentence) > max_chars:  # tek cümle çok uzunsa kelime sınırından böl
            cut = sentence.rfind(" ", 0, max_chars)
            cut = cut if cut > 0 else max_chars
            if current:
                pieces.append(current)
                current = ""
            pieces.append(sentence[:cut].strip())
            sentence = sentence[cut:].strip()
        candidate = f"{current} {sentence}".strip()
        if len(candidate) > max_chars and current:
            pieces.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        pieces.append(current)
    return pieces


def _pack(texts: list[str], max_chars: int) -> list[str]:
    pieces: list[str] = []
    current = ""
    for text in texts:
        for part in _split_long(text, max_chars):
            candidate = f"{current}\n{part}" if current else part
            if len(candidate) > max_chars and current:
                pieces.append(current)
                current = part
            else:
                current = candidate
    if current:
        pieces.append(current)
    return pieces


def chunk_document(doc: Document, max_chars: int = DEFAULT_MAX_CHARS) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    stack: list[tuple[int, str]] = []
    texts: list[str] = []

    def flush() -> None:
        if not texts:
            return
        path = " > ".join(title for _, title in stack) or None
        for piece in _pack(texts, max_chars):
            chunks.append(ChunkDraft(ordinal=len(chunks), heading_path=path, content=piece))
        texts.clear()

    previous_kind = None
    for block in doc.blocks:
        if block.kind == "heading":
            flush()
            if previous_kind == "heading" and stack and stack[-1][0] == block.level:
                # Aralarında metin olmayan aynı düzeydeki başlıklar tek başlıktır (çok satırlı).
                stack[-1] = (block.level, f"{stack[-1][1]} {block.text}")
            else:
                while stack and stack[-1][0] >= block.level:
                    stack.pop()
                stack.append((block.level, block.text))
        else:
            texts.append(block.text)
        previous_kind = block.kind
    flush()
    return chunks

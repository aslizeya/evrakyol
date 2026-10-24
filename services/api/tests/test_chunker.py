from app.ingest.chunker import ChunkDraft, chunk_document
from app.ingest.extract import Block, Document


def doc(*blocks: Block) -> Document:
    return Document(title=None, blocks=list(blocks))


def test_heading_paths_follow_hierarchy() -> None:
    chunks = chunk_document(
        doc(
            Block("heading", "Trafik Tescil", 1),
            Block("heading", "A- Yeni Kayıt", 3),
            Block("text", "1- Fatura,"),
            Block("heading", "E- Veraset", 3),
            Block("text", "1- Mirasçılık belgesi,"),
            Block("text", "2- Kimlik,"),
        )
    )
    assert chunks == [
        ChunkDraft(0, "Trafik Tescil > A- Yeni Kayıt", "1- Fatura,"),
        ChunkDraft(1, "Trafik Tescil > E- Veraset", "1- Mirasçılık belgesi,\n2- Kimlik,"),
    ]


def test_consecutive_same_level_headings_are_merged() -> None:
    chunks = chunk_document(
        doc(
            Block("heading", "ÜLKELERE GÖRE GEÇERLİLİK", 3),
            Block("heading", "(MART 2015)", 3),
            Block("text", "Almanya | 6 ay"),
        )
    )
    assert chunks[0].heading_path == "ÜLKELERE GÖRE GEÇERLİLİK (MART 2015)"


def test_long_sections_are_split_without_exceeding_limit() -> None:
    sentence = "Bu bir örnek cümledir ve belgeyi uzatır. "
    chunks = chunk_document(
        doc(Block("heading", "Uzun", 2), Block("text", sentence * 100)), max_chars=300
    )
    assert len(chunks) > 1
    assert all(len(c.content) <= 300 for c in chunks)
    assert all(c.heading_path == "Uzun" for c in chunks)
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))


def test_single_very_long_word_run_is_hard_split() -> None:
    chunks = chunk_document(doc(Block("text", "kelime " * 500)), max_chars=200)
    assert all(len(c.content) <= 200 for c in chunks)


def test_headings_without_text_produce_no_chunks() -> None:
    assert chunk_document(doc(Block("heading", "Boş bölüm", 2))) == []


def test_embedding_text_carries_context() -> None:
    chunk = ChunkDraft(0, "Mirasçılık > Noterden nasıl alınır?", "Kimlik belgesi")
    assert chunk.embedding_text("TNB") == "TNB\nMirasçılık > Noterden nasıl alınır?\nKimlik belgesi"

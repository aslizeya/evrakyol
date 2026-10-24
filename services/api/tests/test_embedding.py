import math

from app.embedding import FakeEmbedder


def test_fake_embedder_is_deterministic_and_normalised() -> None:
    embedder = FakeEmbedder(dim=1024)
    a, b = embedder.embed_documents(["mirasçılık belgesi", "araç devri"])
    assert len(a) == 1024
    assert a == embedder.embed_query("mirasçılık belgesi")
    assert a != b
    assert math.isclose(sum(v * v for v in a), 1.0, rel_tol=1e-9)

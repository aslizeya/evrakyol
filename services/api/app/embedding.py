"""Embedding katmanı. Varsayılan model kendi sunucumuzda çalışan BAAI/bge-m3'tür (1024 boyut).

Testlerde ve model indirilmeden yapılan denemelerde `FakeEmbedder` kullanılır.
"""

import hashlib
import math
import threading
from functools import lru_cache
from typing import Protocol

from app.config import get_settings


class Embedder(Protocol):
    dim: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class BgeM3Embedder:
    """sentence-transformers ile bge-m3. Model ilk kullanımda indirilir (~2 GB) ve önbelleklenir."""

    def __init__(self, model_name: str = "BAAI/bge-m3", dim: int = 1024, batch_size: int = 16):
        self.model_name = model_name
        self.dim = dim
        self.batch_size = batch_size
        self._model = None
        self._lock = threading.Lock()

    def _load(self):
        with self._lock:
            if self._model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                except ImportError as exc:  # pragma: no cover - kurulum hatası
                    raise RuntimeError(
                        "sentence-transformers kurulu değil: pip install -e '.[embeddings]'"
                    ) from exc
                self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._load().encode(
            texts, batch_size=self.batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        result = [v.tolist() for v in vectors]
        if result and len(result[0]) != self.dim:
            raise RuntimeError(f"Model {len(result[0])} boyut üretti, beklenen {self.dim}")
        return result

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


class FakeEmbedder:
    """Deterministik, modelsiz embedding. Aynı metin her zaman aynı birim vektörü verir."""

    def __init__(self, dim: int = 1024):
        self.dim = dim

    def _vector(self, text: str) -> list[float]:
        values: list[float] = []
        counter = 0
        while len(values) < self.dim:
            digest = hashlib.sha256(f"{counter}:{text}".encode()).digest()
            values.extend((b - 127.5) / 127.5 for b in digest)
            counter += 1
        values = values[: self.dim]
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    if settings.embedding_backend == "fake":
        return FakeEmbedder(settings.embedding_dim)
    return BgeM3Embedder(settings.embedding_model, settings.embedding_dim)

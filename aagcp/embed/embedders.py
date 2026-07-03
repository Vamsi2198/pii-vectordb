"""
Embedder adapters.

HashingEmbedder   — deterministic, dependency-free; proves all logic here.
SentenceTransformerEmbedder — real model (all-MiniLM-L6-v2 etc.); written
                    against the real API, enabled when the package is
                    installed. Same interface, so the engine is unchanged.
"""

from __future__ import annotations
import hashlib
import re
from abc import ABC, abstractmethod
from typing import List
import numpy as np


class EmbedderAdapter(ABC):
    dim: int
    name: str

    @abstractmethod
    def embed(self, text: str) -> np.ndarray: ...

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        return np.vstack([self.embed(t) for t in texts])


class HashingEmbedder(EmbedderAdapter):
    """Feature-hashing over words + char trigrams. Deterministic, no deps."""
    name = "hashing"

    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, text: str) -> np.ndarray:
        text = text.lower()
        words = re.findall(r"[a-z0-9<>_]+", text)
        feats = list(words)
        joined = " ".join(words)
        feats += [joined[i:i+3] for i in range(len(joined) - 2)]
        v = np.zeros(self.dim, dtype=np.float32)
        for f in feats:
            h = int(hashlib.md5(f.encode()).hexdigest(), 16)
            v[h % self.dim] += 1.0 if (h >> 1) % 2 else -1.0
        n = np.linalg.norm(v)
        return v / n if n else v


class SentenceTransformerEmbedder(EmbedderAdapter):
    """
    Real semantic embeddings. pip install sentence-transformers.
        emb = SentenceTransformerEmbedder("all-MiniLM-L6-v2")
    Normalizes to unit length so inner product == cosine (matches the stores).
    """
    name = "sentence_transformers"

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer
        self._m = SentenceTransformer(model_name)
        self.dim = self._m.get_sentence_embedding_dimension()

    def embed(self, text: str) -> np.ndarray:
        return self._m.encode(text, normalize_embeddings=True).astype(np.float32)

    def embed_batch(self, texts):
        return self._m.encode(texts, normalize_embeddings=True).astype(np.float32)

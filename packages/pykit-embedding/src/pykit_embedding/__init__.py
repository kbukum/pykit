"""pykit-embedding — Embedding provider abstractions mirroring rskit-embedding.

Vendor-specific implementations (e.g. OpenAI) live in separate packages
such as ``pykit-openai``.
"""

from __future__ import annotations

from pykit_embedding.provider import EmbeddingError, EmbeddingProvider
from pykit_embedding.types import (
    Embedding,
    cosine_similarity,
    dot_product,
    euclidean_distance,
    max_pooling,
    mean_pooling,
)

__all__ = [
    "Embedding",
    "EmbeddingError",
    "EmbeddingProvider",
    "cosine_similarity",
    "dot_product",
    "euclidean_distance",
    "max_pooling",
    "mean_pooling",
]

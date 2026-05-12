"""pykit-embedding — canonical embedding abstractions and utilities."""

from __future__ import annotations

from pykit_ai.vector import (
    cosine_similarity,
    dot_product,
    euclidean_distance,
    max_pooling,
    mean_pooling,
)
from pykit_embedding.provider import (
    EmbeddingError,
    EmbeddingProvider,
    InMemoryProvider,
    Provider,
    ProviderBase,
)
from pykit_embedding.types import (
    Audio,
    Embedding,
    EmbedInput,
    EmbedRequest,
    EmbedResponse,
    Image,
    Text,
    Video,
)

__all__ = [
    "Audio",
    "EmbedInput",
    "EmbedRequest",
    "EmbedResponse",
    "Embedding",
    "EmbeddingError",
    "EmbeddingProvider",
    "Image",
    "InMemoryProvider",
    "Provider",
    "ProviderBase",
    "Text",
    "Video",
    "cosine_similarity",
    "dot_product",
    "euclidean_distance",
    "max_pooling",
    "mean_pooling",
]

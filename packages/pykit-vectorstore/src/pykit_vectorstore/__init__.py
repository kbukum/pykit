"""pykit-vectorstore — Vector similarity search store mirroring rskit-vectorstore."""

from __future__ import annotations

from pykit_vectorstore.memory import InMemoryVectorStore
from pykit_vectorstore.registry import VectorStoreRegistry, default_vectorstore_registry, register_memory
from pykit_vectorstore.store import (
    FilterValue,
    PointPayload,
    SearchFilter,
    SearchResult,
    VectorMetric,
    VectorStore,
    VectorStoreConfig,
    VectorStoreError,
)

__all__ = [
    "FilterValue",
    "InMemoryVectorStore",
    "PointPayload",
    "SearchFilter",
    "SearchResult",
    "VectorMetric",
    "VectorStore",
    "VectorStoreConfig",
    "VectorStoreError",
    "VectorStoreRegistry",
    "default_vectorstore_registry",
    "register_memory",
]

"""Tests for vector store protocol compliance."""

from __future__ import annotations

from pykit_vector_store.memory import InMemoryVectorStore
from pykit_vector_store.store import PointPayload, VectorStore


class TestVectorStoreProtocol:
    def test_in_memory_implements_protocol(self) -> None:
        store = InMemoryVectorStore()
        assert isinstance(store, VectorStore)

    async def test_full_lifecycle(self) -> None:
        """Test the complete CRUD lifecycle through the protocol."""
        store: VectorStore = InMemoryVectorStore()

        await store.ensure_collection("docs", 3)
        await store.upsert("docs", "d1", [1.0, 0.0, 0.0], PointPayload(fields={"title": "A"}))
        await store.upsert("docs", "d2", [0.0, 1.0, 0.0], PointPayload(fields={"title": "B"}))

        results = await store.search("docs", [1.0, 0.0, 0.0], 5)
        assert len(results) == 2
        assert results[0].id == "d1"

        await store.delete("docs", "d1")
        results = await store.search("docs", [1.0, 0.0, 0.0], 5)
        assert len(results) == 1
        assert results[0].id == "d2"

"""Tests for vector store protocol compliance."""

from __future__ import annotations

from pykit_vectorstore.memory import InMemoryVectorStore
from pykit_vectorstore.registry import VectorStoreRegistry, default_vectorstore_registry, register_memory
from pykit_vectorstore.store import PointPayload, VectorStore


class TestVectorStoreProtocol:
    def test_empty_registry_has_no_side_effect_backends(self) -> None:
        registry = VectorStoreRegistry()
        assert registry.names() == ()

    def test_explicit_memory_registration(self) -> None:
        registry = VectorStoreRegistry()
        register_memory(registry)
        assert registry.names() == ("memory",)

    def test_default_registry_only_contains_memory(self) -> None:
        assert default_vectorstore_registry().names() == ("memory",)

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

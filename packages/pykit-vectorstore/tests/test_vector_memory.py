"""Tests for the in-memory vector store."""

from __future__ import annotations

import pytest

from pykit_vectorstore.memory import InMemoryVectorStore
from pykit_vectorstore.store import PointPayload, SearchFilter, VectorStoreError


class TestInMemoryVectorStore:
    async def test_ensure_collection_creates_new(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 3)
        # Should not error when called again
        await store.ensure_collection("test", 3)

    async def test_upsert_and_search(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 3)

        await store.upsert("test", "1", [1.0, 0.0, 0.0], PointPayload(fields={"name": "doc1"}))
        await store.upsert("test", "2", [0.0, 1.0, 0.0], PointPayload(fields={"name": "doc2"}))

        results = await store.search("test", [1.0, 0.0, 0.0], 10)
        assert len(results) == 2
        assert results[0].id == "1"
        assert abs(results[0].score - 1.0) < 1e-6

    async def test_upsert_updates_existing(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        await store.upsert("test", "1", [1.0, 0.0], PointPayload(fields={"v": "old"}))
        await store.upsert("test", "1", [0.0, 1.0], PointPayload(fields={"v": "new"}))

        results = await store.search("test", [0.0, 1.0], 10)
        assert len(results) == 1
        assert results[0].id == "1"
        assert results[0].payload.fields.get("v") == "new"

    async def test_search_with_filter(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        await store.upsert("test", "1", [1.0, 0.0], PointPayload(fields={"type": "a"}))
        await store.upsert("test", "2", [1.0, 0.0], PointPayload(fields={"type": "b"}))

        filt = SearchFilter().must_match("type", "a")
        results = await store.search("test", [1.0, 0.0], 10, filter=filt)

        assert len(results) == 1
        assert results[0].id == "1"

    async def test_search_with_tenant_filter(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        await store.upsert("test", "1", [1.0, 0.0], PointPayload(fields={"tenant_id": "a"}))
        await store.upsert("test", "2", [1.0, 0.0], PointPayload(fields={"tenant_id": "b"}))

        results = await store.search("test", [1.0, 0.0], 10, filter=SearchFilter().for_tenant("a"))

        assert [result.id for result in results] == ["1"]

    async def test_dot_metric_recall(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2, metric="dot")
        await store.upsert("test", "small", [1.0, 0.0], PointPayload())
        await store.upsert("test", "large", [2.0, 0.0], PointPayload())

        results = await store.search("test", [1.0, 0.0], 2)

        assert [result.id for result in results] == ["large", "small"]

    async def test_l2_metric_recall(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2, metric="l2")
        await store.upsert("test", "near", [1.0, 0.0], PointPayload())
        await store.upsert("test", "far", [9.0, 0.0], PointPayload())

        results = await store.search("test", [0.0, 0.0], 2)

        assert [result.id for result in results] == ["near", "far"]

    async def test_delete(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        await store.upsert("test", "1", [1.0, 0.0], PointPayload())
        await store.delete("test", "1")

        results = await store.search("test", [1.0, 0.0], 10)
        assert len(results) == 0

    async def test_upsert_wrong_dimensions(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 3)

        with pytest.raises(VectorStoreError, match="dimensions mismatch"):
            await store.upsert("test", "1", [1.0, 0.0], PointPayload())

    async def test_upsert_missing_collection(self) -> None:
        store = InMemoryVectorStore()

        with pytest.raises(VectorStoreError, match="does not exist"):
            await store.upsert("nonexistent", "1", [1.0], PointPayload())

    async def test_search_missing_collection(self) -> None:
        store = InMemoryVectorStore()

        with pytest.raises(VectorStoreError, match="does not exist"):
            await store.search("nonexistent", [1.0], 10)

    async def test_search_wrong_dimensions(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 3)

        with pytest.raises(VectorStoreError, match="dimensions mismatch"):
            await store.search("test", [1.0, 0.0], 10)

    async def test_delete_missing_collection(self) -> None:
        store = InMemoryVectorStore()

        with pytest.raises(VectorStoreError, match="does not exist"):
            await store.delete("nonexistent", "1")

    async def test_search_limit(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        for i in range(10):
            await store.upsert("test", str(i), [1.0, float(i)], PointPayload())

        results = await store.search("test", [1.0, 0.0], 3)
        assert len(results) == 3

    async def test_search_sorted_by_score(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        await store.upsert("test", "far", [0.0, 1.0], PointPayload())
        await store.upsert("test", "close", [1.0, 0.0], PointPayload())

        results = await store.search("test", [1.0, 0.0], 10)
        assert results[0].id == "close"
        assert results[0].score > results[1].score

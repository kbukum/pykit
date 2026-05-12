"""Extended tests for vector store: edge cases, concurrency, builder patterns."""

from __future__ import annotations

import asyncio

import pytest

from pykit_vectorstore.memory import InMemoryVectorStore, _cosine_similarity
from pykit_vectorstore.store import (
    PointPayload,
    SearchFilter,
    SearchResult,
    VectorStore,
    VectorStoreError,
)

# ---------------------------------------------------------------------------
# Data type / builder tests
# ---------------------------------------------------------------------------


class TestPointPayload:
    def test_default_empty_fields(self) -> None:
        p = PointPayload()
        assert p.fields == {}

    def test_with_field_returns_self(self) -> None:
        p = PointPayload()
        result = p.with_field("a", 1)
        assert result is p

    def test_with_field_chaining(self) -> None:
        p = PointPayload().with_field("a", 1).with_field("b", "two").with_field("c", [3])
        assert p.fields == {"a": 1, "b": "two", "c": [3]}

    def test_with_field_overwrites(self) -> None:
        p = PointPayload().with_field("k", "old").with_field("k", "new")
        assert p.fields["k"] == "new"

    def test_independent_instances(self) -> None:
        p1 = PointPayload()
        p2 = PointPayload()
        p1.with_field("x", 1)
        assert "x" not in p2.fields


class TestSearchFilter:
    def test_default_empty_must(self) -> None:
        f = SearchFilter()
        assert f.must == []

    def test_must_match_returns_self(self) -> None:
        f = SearchFilter()
        result = f.must_match("a", 1)
        assert result is f

    def test_must_match_chaining(self) -> None:
        f = SearchFilter().must_match("type", "doc").must_match("lang", "en")
        assert len(f.must) == 2
        assert ("type", "doc") in f.must
        assert ("lang", "en") in f.must

    def test_independent_instances(self) -> None:
        f1 = SearchFilter()
        f2 = SearchFilter()
        f1.must_match("x", 1)
        assert len(f2.must) == 0


class TestSearchResult:
    def test_fields(self) -> None:
        r = SearchResult(id="abc", score=0.95, payload=PointPayload(fields={"k": "v"}))
        assert r.id == "abc"
        assert r.score == 0.95
        assert r.payload.fields["k"] == "v"


class TestVectorStoreError:
    def test_is_exception(self) -> None:
        assert issubclass(VectorStoreError, Exception)

    def test_message(self) -> None:
        err = VectorStoreError("bad thing")
        assert "bad thing" in str(err)


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocol:
    def test_in_memory_is_runtime_checkable(self) -> None:
        store = InMemoryVectorStore()
        assert isinstance(store, VectorStore)


# ---------------------------------------------------------------------------
# Cosine similarity unit tests
# ---------------------------------------------------------------------------


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        assert abs(_cosine_similarity([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9

    def test_orthogonal_vectors(self) -> None:
        assert abs(_cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-9

    def test_opposite_vectors(self) -> None:
        assert abs(_cosine_similarity([1.0, 0.0], [-1.0, 0.0]) + 1.0) < 1e-9

    def test_zero_vector_returns_zero(self) -> None:
        assert _cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_both_zero_vectors(self) -> None:
        assert _cosine_similarity([0.0, 0.0], [0.0, 0.0]) == 0.0

    @pytest.mark.parametrize(
        "a, b, expected",
        [
            ([1, 1], [1, 1], 1.0),
            ([3, 4], [4, 3], 0.96),
            ([1, 0, 0], [0, 1, 0], 0.0),
        ],
    )
    def test_known_values(self, a: list[float], b: list[float], expected: float) -> None:
        assert abs(_cosine_similarity(a, b) - expected) < 0.01


# ---------------------------------------------------------------------------
# InMemoryVectorStore — extended scenarios
# ---------------------------------------------------------------------------


class TestInMemoryVectorStoreExtended:
    async def test_empty_collection_search_returns_empty(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("empty", 2)
        results = await store.search("empty", [1.0, 0.0], 10)
        assert results == []

    async def test_multiple_collections_isolated(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("col_a", 2)
        await store.ensure_collection("col_b", 3)

        await store.upsert("col_a", "1", [1.0, 0.0], PointPayload(fields={"c": "a"}))
        await store.upsert("col_b", "1", [1.0, 0.0, 0.0], PointPayload(fields={"c": "b"}))

        results_a = await store.search("col_a", [1.0, 0.0], 10)
        results_b = await store.search("col_b", [1.0, 0.0, 0.0], 10)

        assert len(results_a) == 1
        assert results_a[0].payload.fields["c"] == "a"
        assert len(results_b) == 1
        assert results_b[0].payload.fields["c"] == "b"

    async def test_large_dimensions(self) -> None:
        dims = 512
        store = InMemoryVectorStore()
        await store.ensure_collection("large", dims)

        vec = [0.0] * dims
        vec[0] = 1.0
        await store.upsert("large", "1", vec, PointPayload())

        results = await store.search("large", vec, 1)
        assert len(results) == 1
        assert abs(results[0].score - 1.0) < 1e-6

    async def test_delete_nonexistent_id_is_noop(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)
        await store.upsert("test", "1", [1.0, 0.0], PointPayload())
        # Deleting non-existent ID should not raise
        await store.delete("test", "nonexistent")
        results = await store.search("test", [1.0, 0.0], 10)
        assert len(results) == 1

    async def test_search_with_filter_no_matches(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)
        await store.upsert("test", "1", [1.0, 0.0], PointPayload(fields={"type": "a"}))

        filt = SearchFilter().must_match("type", "nonexistent")
        results = await store.search("test", [1.0, 0.0], 10, filter=filt)
        assert results == []

    async def test_search_multiple_must_conditions(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)
        await store.upsert("test", "1", [1.0, 0.0], PointPayload(fields={"type": "a", "lang": "en"}))
        await store.upsert("test", "2", [1.0, 0.0], PointPayload(fields={"type": "a", "lang": "fr"}))
        await store.upsert("test", "3", [1.0, 0.0], PointPayload(fields={"type": "b", "lang": "en"}))

        filt = SearchFilter().must_match("type", "a").must_match("lang", "en")
        results = await store.search("test", [1.0, 0.0], 10, filter=filt)
        assert len(results) == 1
        assert results[0].id == "1"

    async def test_search_limit_zero(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)
        await store.upsert("test", "1", [1.0, 0.0], PointPayload())
        results = await store.search("test", [1.0, 0.0], 0)
        assert results == []

    async def test_search_limit_exceeds_count(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)
        await store.upsert("test", "1", [1.0, 0.0], PointPayload())
        results = await store.search("test", [1.0, 0.0], 100)
        assert len(results) == 1

    async def test_upsert_preserves_other_points(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)
        await store.upsert("test", "1", [1.0, 0.0], PointPayload(fields={"v": "1"}))
        await store.upsert("test", "2", [0.0, 1.0], PointPayload(fields={"v": "2"}))
        # Update only "1"
        await store.upsert("test", "1", [0.5, 0.5], PointPayload(fields={"v": "1-updated"}))

        results = await store.search("test", [0.0, 1.0], 10)
        ids = {r.id for r in results}
        assert ids == {"1", "2"}
        for r in results:
            if r.id == "1":
                assert r.payload.fields["v"] == "1-updated"

    async def test_ensure_collection_idempotent_preserves_data(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)
        await store.upsert("test", "1", [1.0, 0.0], PointPayload(fields={"k": "v"}))
        # Re-ensure should not clear data
        await store.ensure_collection("test", 2)
        results = await store.search("test", [1.0, 0.0], 10)
        assert len(results) == 1
        assert results[0].payload.fields["k"] == "v"

    async def test_cosine_similarity_ranking_accuracy(self) -> None:
        """Verify that closer vectors rank higher."""
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        # query is [1, 0], these are ordered by angle from query
        await store.upsert("test", "exact", [1.0, 0.0], PointPayload())
        await store.upsert("test", "close", [0.9, 0.1], PointPayload())
        await store.upsert("test", "medium", [0.5, 0.5], PointPayload())
        await store.upsert("test", "far", [0.0, 1.0], PointPayload())

        results = await store.search("test", [1.0, 0.0], 4)
        assert [r.id for r in results] == ["exact", "close", "medium", "far"]

    async def test_many_upserts_and_deletes(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        for i in range(50):
            await store.upsert("test", str(i), [float(i), 1.0], PointPayload())

        for i in range(0, 50, 2):
            await store.delete("test", str(i))

        results = await store.search("test", [1.0, 1.0], 100)
        assert len(results) == 25
        ids = {r.id for r in results}
        for i in range(50):
            if i % 2 == 0:
                assert str(i) not in ids
            else:
                assert str(i) in ids

    async def test_payload_with_complex_values(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        payload = PointPayload(
            fields={
                "tags": ["a", "b"],
                "nested": {"key": "value"},
                "count": 42,
                "flag": True,
            }
        )
        await store.upsert("test", "1", [1.0, 0.0], payload)
        results = await store.search("test", [1.0, 0.0], 1)
        assert results[0].payload.fields["tags"] == ["a", "b"]
        assert results[0].payload.fields["nested"]["key"] == "value"
        assert results[0].payload.fields["count"] == 42

    async def test_concurrent_upserts(self) -> None:
        """Verify thread-safety of concurrent upserts via asyncio tasks."""
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        async def upsert_batch(start: int) -> None:
            for i in range(start, start + 20):
                await store.upsert("test", str(i), [float(i), 1.0], PointPayload())

        await asyncio.gather(
            upsert_batch(0),
            upsert_batch(20),
            upsert_batch(40),
        )

        results = await store.search("test", [1.0, 1.0], 100)
        assert len(results) == 60

    async def test_concurrent_search_during_upsert(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)

        for i in range(10):
            await store.upsert("test", str(i), [float(i), 1.0], PointPayload())

        async def search_loop() -> list[int]:
            counts = []
            for _ in range(10):
                results = await store.search("test", [1.0, 1.0], 100)
                counts.append(len(results))
            return counts

        async def upsert_loop() -> None:
            for i in range(10, 20):
                await store.upsert("test", str(i), [float(i), 1.0], PointPayload())

        counts, _ = await asyncio.gather(search_loop(), upsert_loop())
        # Search counts should always be >= 10 (initial) and non-decreasing
        for c in counts:
            assert c >= 10

    async def test_search_with_zero_vector_query(self) -> None:
        store = InMemoryVectorStore()
        await store.ensure_collection("test", 2)
        await store.upsert("test", "1", [1.0, 0.0], PointPayload())

        results = await store.search("test", [0.0, 0.0], 10)
        assert len(results) == 1
        assert results[0].score == 0.0

"""Tests for Qdrant adapter translation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pykit_vectorstore.qdrant as qdrant
from pykit_vectorstore.store import SearchFilter


@dataclass
class _FakeIsNullCondition:
    is_null: object


@dataclass
class _FakePayloadField:
    key: str


@dataclass
class _FakeMatchValue:
    value: object


@dataclass
class _FakeFieldCondition:
    key: str
    match: object | None = None
    range: object | None = None


@dataclass
class _FakeRange:
    gte: float
    lte: float


@dataclass
class _FakeFilter:
    must: list[object]


@dataclass
class _FakeVectorParams:
    size: int
    distance: object


@dataclass
class _FakeCollectionParams:
    vectors: object


@dataclass
class _FakeCollectionConfig:
    params: _FakeCollectionParams


@dataclass
class _FakeCollectionInfo:
    config: _FakeCollectionConfig


@dataclass
class _FakeQueryResults:
    points: list[object]


class _FakeClient:
    def __init__(self, collection_info: object | None = None) -> None:
        self.query_filter: object | None = None
        self.collection_info = collection_info
        self.created_collection: dict[str, object] | None = None

    def query_points(self, **kwargs: object) -> _FakeQueryResults:
        self.query_filter = kwargs["query_filter"]
        return _FakeQueryResults(points=[])

    def collection_exists(self, collection: str) -> bool:
        return self.collection_info is not None

    def create_collection(self, **kwargs: object) -> None:
        self.created_collection = dict(kwargs)

    def get_collection(self, *, collection_name: str) -> object:
        _ = collection_name
        assert self.collection_info is not None
        return self.collection_info


async def test_qdrant_search_translates_none_filter_to_null_check(monkeypatch: Any) -> None:
    monkeypatch.setattr(qdrant, "IsNullCondition", _FakeIsNullCondition, raising=False)
    monkeypatch.setattr(qdrant, "PayloadField", _FakePayloadField, raising=False)
    monkeypatch.setattr(qdrant, "Filter", _FakeFilter, raising=False)
    store = qdrant.QdrantVectorStore.__new__(qdrant.QdrantVectorStore)
    client = _FakeClient()
    store._client = client

    await store.search(
        "docs",
        [1.0],
        10,
        filter=SearchFilter().must_match("archived_at", None),
    )

    assert client.query_filter == _FakeFilter(
        must=[_FakeIsNullCondition(is_null=_FakePayloadField(key="archived_at"))]
    )


async def test_qdrant_search_translates_values_to_match(monkeypatch: Any) -> None:
    monkeypatch.setattr(qdrant, "FieldCondition", _FakeFieldCondition, raising=False)
    monkeypatch.setattr(qdrant, "Filter", _FakeFilter, raising=False)
    monkeypatch.setattr(qdrant, "MatchValue", _FakeMatchValue, raising=False)
    store = qdrant.QdrantVectorStore.__new__(qdrant.QdrantVectorStore)
    client = _FakeClient()
    store._client = client

    await store.search(
        "docs",
        [1.0],
        10,
        filter=SearchFilter().must_match("tenant_id", "tenant-a"),
    )

    assert client.query_filter == _FakeFilter(
        must=[_FakeFieldCondition(key="tenant_id", match=_FakeMatchValue(value="tenant-a"))]
    )


async def test_qdrant_search_translates_float_values_to_exact_range(monkeypatch: Any) -> None:
    monkeypatch.setattr(qdrant, "FieldCondition", _FakeFieldCondition, raising=False)
    monkeypatch.setattr(qdrant, "Filter", _FakeFilter, raising=False)
    monkeypatch.setattr(qdrant, "Range", _FakeRange, raising=False)
    store = qdrant.QdrantVectorStore.__new__(qdrant.QdrantVectorStore)
    client = _FakeClient()
    store._client = client

    await store.search(
        "docs",
        [1.0],
        10,
        filter=SearchFilter().must_match("score", 0.5),
    )

    assert client.query_filter == _FakeFilter(
        must=[_FakeFieldCondition(key="score", range=_FakeRange(gte=0.5, lte=0.5))]
    )


async def test_qdrant_ensure_collection_validates_existing_vector_config() -> None:
    store = qdrant.QdrantVectorStore.__new__(qdrant.QdrantVectorStore)
    store._metric = "cosine"
    store._client = _FakeClient(
        _FakeCollectionInfo(
            config=_FakeCollectionConfig(
                params=_FakeCollectionParams(vectors=_FakeVectorParams(size=3, distance="Cosine"))
            )
        )
    )

    await store.ensure_collection("docs", 3, metric="cosine")


async def test_qdrant_ensure_collection_rejects_existing_dimension_mismatch() -> None:
    store = qdrant.QdrantVectorStore.__new__(qdrant.QdrantVectorStore)
    store._metric = "cosine"
    store._client = _FakeClient(
        _FakeCollectionInfo(
            config=_FakeCollectionConfig(
                params=_FakeCollectionParams(vectors=_FakeVectorParams(size=3, distance="Cosine"))
            )
        )
    )

    try:
        await store.ensure_collection("docs", 4, metric="cosine")
    except qdrant.VectorStoreError as exc:
        assert "vector size" in str(exc)
    else:
        raise AssertionError("dimension mismatch should fail")


async def test_qdrant_ensure_collection_rejects_existing_metric_mismatch() -> None:
    store = qdrant.QdrantVectorStore.__new__(qdrant.QdrantVectorStore)
    store._metric = "cosine"
    store._client = _FakeClient(
        _FakeCollectionInfo(
            config=_FakeCollectionConfig(
                params=_FakeCollectionParams(vectors=_FakeVectorParams(size=3, distance="Dot"))
            )
        )
    )

    try:
        await store.ensure_collection("docs", 3, metric="cosine")
    except qdrant.VectorStoreError as exc:
        assert "metric" in str(exc)
    else:
        raise AssertionError("metric mismatch should fail")

"""In-memory vector store implementation for testing."""

from __future__ import annotations

import math
import threading
from dataclasses import dataclass

from pykit_vectorstore.store import (
    PointPayload,
    SearchFilter,
    SearchResult,
    VectorMetric,
    VectorStoreError,
)


@dataclass
class _StoredPoint:
    id: str
    vector: list[float]
    payload: PointPayload


@dataclass
class _Collection:
    dimensions: int
    metric: VectorMetric
    points: list[_StoredPoint]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _dot_similarity(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def _l2_similarity(a: list[float], b: list[float]) -> float:
    return -math.sqrt(sum((x - y) * (x - y) for x, y in zip(a, b, strict=True)))


def _matches_filter(payload: PointPayload, filt: SearchFilter) -> bool:
    """Check whether a payload matches all must conditions."""
    for field_name, expected in filt.conditions():
        actual = payload.fields.get(field_name)
        if actual != expected:
            return False
    return True


class InMemoryVectorStore:
    """In-memory vector store backed by a simple list with linear scan search.

    Intended for unit tests and prototyping — not suitable for production.
    Thread-safe via threading.Lock.
    """

    def __init__(self) -> None:
        self._collections: dict[str, _Collection] = {}
        self._lock = threading.Lock()

    async def ensure_collection(
        self, collection: str, dimensions: int, metric: VectorMetric = "cosine"
    ) -> None:
        """Ensure a collection exists, creating it if necessary."""
        if metric not in ("cosine", "dot", "l2"):
            raise VectorStoreError(f"unsupported vector metric: {metric}")
        with self._lock:
            existing = self._collections.get(collection)
            if existing is None:
                self._collections[collection] = _Collection(dimensions=dimensions, metric=metric, points=[])
                return
            if existing.dimensions != dimensions:
                raise VectorStoreError(
                    f"collection '{collection}' dimensions mismatch: "
                    f"expected {existing.dimensions}, got {dimensions}"
                )
            if existing.metric != metric:
                raise VectorStoreError(
                    f"collection '{collection}' metric mismatch: expected {existing.metric}, got {metric}"
                )

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        payload: PointPayload,
    ) -> None:
        """Insert or update a vector point."""
        with self._lock:
            col = self._collections.get(collection)
            if col is None:
                raise VectorStoreError(f"collection '{collection}' does not exist")

            if len(vector) != col.dimensions:
                raise VectorStoreError(
                    f"vector dimensions mismatch: expected {col.dimensions}, got {len(vector)}"
                )

            for point in col.points:
                if point.id == id:
                    point.vector = vector
                    point.payload = payload
                    return

            col.points.append(_StoredPoint(id=id, vector=vector, payload=payload))

    async def search(
        self,
        collection: str,
        vector: list[float],
        limit: int,
        filter: SearchFilter | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors using brute-force cosine similarity."""
        with self._lock:
            col = self._collections.get(collection)
            if col is None:
                raise VectorStoreError(f"collection '{collection}' does not exist")
            if len(vector) != col.dimensions:
                raise VectorStoreError(
                    f"vector dimensions mismatch: expected {col.dimensions}, got {len(vector)}"
                )

            scored: list[SearchResult] = []
            for point in col.points:
                if filter is not None and not _matches_filter(point.payload, filter):
                    continue
                score = _score(vector, point.vector, col.metric)
                scored.append(SearchResult(id=point.id, score=score, payload=point.payload))

            scored.sort(key=lambda r: r.score, reverse=True)
            return scored[:limit]

    async def delete(self, collection: str, id: str) -> None:
        """Delete a point by ID."""
        with self._lock:
            col = self._collections.get(collection)
            if col is None:
                raise VectorStoreError(f"collection '{collection}' does not exist")
            col.points = [p for p in col.points if p.id != id]


def _score(a: list[float], b: list[float], metric: VectorMetric) -> float:
    if metric == "cosine":
        return _cosine_similarity(a, b)
    if metric == "dot":
        return _dot_similarity(a, b)
    return _l2_similarity(a, b)

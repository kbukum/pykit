"""Qdrant vector store implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykit_vectorstore.store import (
    PointPayload,
    SearchFilter,
    SearchResult,
    VectorMetric,
    VectorStoreConfig,
    VectorStoreError,
)

if TYPE_CHECKING:
    from pykit_vectorstore.registry import VectorStoreRegistry

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        FieldCondition,
        Filter,
        MatchValue,
        PointStruct,
        VectorParams,
    )

    _HAS_QDRANT = True
except ImportError:
    _HAS_QDRANT = False


@dataclass
class QdrantConfig:
    """Configuration for the Qdrant vector store."""

    url: str = "http://localhost:6333"
    api_key: str | None = None
    metric: VectorMetric = "cosine"


class QdrantVectorStore:
    """Qdrant-backed vector store.

    Requires ``qdrant-client`` to be installed
    (``pip install pykit-vectorstore[qdrant]``).
    """

    def __init__(self, config: QdrantConfig | None = None) -> None:
        if not _HAS_QDRANT:
            raise ImportError(
                "qdrant-client is required for QdrantVectorStore. "
                "Install with: pip install pykit-vectorstore[qdrant]"
            )
        cfg = config or QdrantConfig()
        self._metric = cfg.metric
        kwargs: dict[str, Any] = {"url": cfg.url}
        if cfg.api_key:
            kwargs["api_key"] = cfg.api_key
        self._client = QdrantClient(**kwargs)

    async def ensure_collection(
        self, collection: str, dimensions: int, metric: VectorMetric = "cosine"
    ) -> None:
        """Ensure a Qdrant collection exists."""
        try:
            if not self._client.collection_exists(collection):
                self._client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(size=dimensions, distance=_to_qdrant_distance(metric)),
                )
        except Exception as exc:
            raise VectorStoreError(f"failed to ensure Qdrant collection: {exc}") from exc

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        payload: PointPayload,
    ) -> None:
        """Upsert a vector point into Qdrant."""
        try:
            self._client.upsert(
                collection_name=collection,
                points=[
                    PointStruct(
                        id=id,
                        vector=vector,
                        payload=payload.fields,
                    )
                ],
                wait=True,
            )
        except Exception as exc:
            raise VectorStoreError(f"failed to upsert to Qdrant: {exc}") from exc

    async def search(
        self,
        collection: str,
        vector: list[float],
        limit: int,
        filter: SearchFilter | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors in Qdrant."""
        query_filter = None
        if filter is not None and filter.conditions():
            conditions = [
                FieldCondition(key=field, match=MatchValue(value=value))
                for field, value in filter.conditions()
            ]
            query_filter = Filter(must=conditions)

        try:
            results = self._client.query_points(
                collection_name=collection,
                query=vector,
                limit=limit,
                query_filter=query_filter,
                with_payload=True,
            )
        except Exception as exc:
            raise VectorStoreError(f"failed to search Qdrant: {exc}") from exc

        return [
            SearchResult(
                id=str(point.id),
                score=point.score or 0.0,
                payload=PointPayload(fields=dict(point.payload or {})),
            )
            for point in results.points
        ]

    async def delete(self, collection: str, id: str) -> None:
        """Delete a point from Qdrant by ID."""
        try:
            self._client.delete(
                collection_name=collection,
                points_selector=[id],
                wait=True,
            )
        except Exception as exc:
            raise VectorStoreError(f"failed to delete from Qdrant: {exc}") from exc


def _to_qdrant_distance(metric: VectorMetric) -> Distance:
    if metric == "cosine":
        return Distance.COSINE
    if metric == "dot":
        return Distance.DOT
    if metric == "l2":
        return Distance.EUCLID
    raise VectorStoreError(f"unsupported Qdrant metric: {metric}")


def _from_config(config: VectorStoreConfig) -> QdrantVectorStore:
    return QdrantVectorStore(
        QdrantConfig(url=config.qdrant_url, api_key=config.qdrant_api_key, metric=config.metric)
    )


def register(registry: VectorStoreRegistry) -> None:
    """Register the Qdrant backend in an injected registry."""
    registry.register("qdrant", _from_config)

"""Qdrant vector store implementation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pykit_errors.codes import ErrorCode
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
        IsNullCondition,
        MatchValue,
        PayloadField,
        PointStruct,
        Range,
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
        self, collection: str, dimensions: int, metric: VectorMetric | None = None
    ) -> None:
        """Ensure a Qdrant collection exists."""
        selected_metric = metric or self._metric
        try:
            if not self._client.collection_exists(collection):
                self._client.create_collection(
                    collection_name=collection,
                    vectors_config=VectorParams(
                        size=dimensions, distance=_to_qdrant_distance(selected_metric)
                    ),
                )
                return
            collection_info = self._client.get_collection(collection_name=collection)
            _validate_collection_config(collection_info, dimensions, selected_metric)
        except VectorStoreError:
            raise
        except Exception as exc:
            raise VectorStoreError(
                f"failed to ensure Qdrant collection: {exc}", ErrorCode.EXTERNAL_SERVICE
            ) from exc

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
            raise VectorStoreError(f"failed to upsert to Qdrant: {exc}", ErrorCode.EXTERNAL_SERVICE) from exc

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
            conditions: list[Any] = [
                _condition_to_qdrant(field, value) for field, value in filter.conditions()
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
            raise VectorStoreError(f"failed to search Qdrant: {exc}", ErrorCode.EXTERNAL_SERVICE) from exc

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
            raise VectorStoreError(
                f"failed to delete from Qdrant: {exc}", ErrorCode.EXTERNAL_SERVICE
            ) from exc


def _to_qdrant_distance(metric: VectorMetric) -> Distance:
    if metric == "cosine":
        return Distance.COSINE
    if metric == "dot":
        return Distance.DOT
    if metric == "l2":
        return Distance.EUCLID
    raise VectorStoreError(f"unsupported Qdrant metric: {metric}")


def _validate_collection_config(info: object, dimensions: int, metric: VectorMetric) -> None:
    vectors = _collection_vectors_config(info)
    if isinstance(vectors, dict):
        raise VectorStoreError(
            "existing Qdrant collection uses named vectors; expected unnamed vector config"
        )
    if vectors is None:
        raise VectorStoreError("existing Qdrant collection has no vector configuration")

    size = _read_field(vectors, "size")
    distance = _read_field(vectors, "distance")
    if size != dimensions:
        raise VectorStoreError(
            f"existing Qdrant collection vector size {size!r} does not match requested dimensions {dimensions}"
        )

    existing_metric = _metric_from_qdrant_distance(distance)
    if existing_metric != metric:
        raise VectorStoreError(
            f"existing Qdrant collection metric {existing_metric!r} does not match requested metric {metric!r}"
        )


def _collection_vectors_config(info: object) -> object | None:
    config = _read_field(info, "config")
    params = _read_field(config, "params")
    return _read_field(params, "vectors") or _read_field(params, "vectors_config")


def _read_field(value: object, name: str) -> object | None:
    if isinstance(value, dict):
        return value.get(name)
    return getattr(value, name, None)


def _metric_from_qdrant_distance(distance: object) -> VectorMetric:
    raw = getattr(distance, "value", distance)
    normalized = raw.lower() if isinstance(raw, str) else str(raw).lower()
    if normalized in {"cosine", "distance.cosine"}:
        return "cosine"
    if normalized in {"dot", "distance.dot"}:
        return "dot"
    if normalized in {"euclid", "euclidean", "distance.euclid"}:
        return "l2"
    raise VectorStoreError(f"unsupported existing Qdrant collection distance: {distance!r}")


def _condition_to_qdrant(field: str, value: object) -> Any:
    if value is None:
        return IsNullCondition(is_null=PayloadField(key=field))
    if isinstance(value, float):
        return FieldCondition(key=field, range=Range(gte=value, lte=value))
    if isinstance(value, (str, int, bool)):
        return FieldCondition(key=field, match=MatchValue(value=value))
    raise VectorStoreError(f"unsupported Qdrant filter value for field '{field}': {value!r}")


def _from_config(config: VectorStoreConfig) -> QdrantVectorStore:
    return QdrantVectorStore(
        QdrantConfig(url=config.qdrant_url, api_key=config.qdrant_api_key, metric=config.metric)
    )


def register(registry: VectorStoreRegistry) -> None:
    """Register the Qdrant backend in an injected registry."""
    registry.register("qdrant", _from_config)

"""Vector store protocol and data types."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

from pykit_errors import AppError
from pykit_errors.codes import ErrorCode

VectorMetric = Literal["cosine", "dot", "l2"]
FilterValue = str | int | float | bool | None
PayloadValue = object


class VectorStoreError(AppError):
    """Raised when a vector store operation fails."""

    def __init__(self, message: str, code: ErrorCode = ErrorCode.INVALID_INPUT) -> None:
        super().__init__(code, message)


@dataclass
class PointPayload:
    """Payload stored alongside each vector point."""

    fields: dict[str, PayloadValue] = field(default_factory=dict)

    def with_field(self, key: str, value: PayloadValue) -> PointPayload:
        """Add a field and return self for chaining."""
        self.fields[key] = value
        return self


@dataclass
class SearchResult:
    """A single search result from the vector store."""

    id: str
    score: float
    payload: PointPayload


@dataclass
class SearchFilter:
    """Optional filters for search queries."""

    must: list[tuple[str, FilterValue]] = field(default_factory=list)
    tenant_id: str | None = None

    def must_match(self, field_name: str, value: FilterValue) -> SearchFilter:
        """Add a must-match condition and return self for chaining."""
        self.must.append((field_name, value))
        return self

    def for_tenant(self, tenant_id: str) -> SearchFilter:
        """Restrict search to a tenant."""
        self.tenant_id = tenant_id
        return self

    def conditions(self) -> tuple[tuple[str, FilterValue], ...]:
        """Return normalized filter conditions including tenant isolation."""
        conditions = list(self.must)
        if self.tenant_id is not None:
            conditions.append(("tenant_id", self.tenant_id))
        return tuple(conditions)


@dataclass(frozen=True)
class VectorStoreConfig:
    """Config-driven vectorstore backend selection."""

    backend: str = "memory"
    metric: VectorMetric = "cosine"
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str | None = None


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector similarity search stores."""

    async def ensure_collection(
        self, collection: str, dimensions: int, metric: VectorMetric | None = None
    ) -> None:
        """Ensure a collection exists, creating it if necessary."""
        ...

    async def upsert(
        self,
        collection: str,
        id: str,
        vector: list[float],
        payload: PointPayload,
    ) -> None:
        """Insert or update a vector point."""
        ...

    async def search(
        self,
        collection: str,
        vector: list[float],
        limit: int,
        filter: SearchFilter | None = None,
    ) -> list[SearchResult]:
        """Search for similar vectors."""
        ...

    async def delete(self, collection: str, id: str) -> None:
        """Delete a point by ID."""
        ...


VectorStoreFactory = Callable[[VectorStoreConfig], VectorStore]

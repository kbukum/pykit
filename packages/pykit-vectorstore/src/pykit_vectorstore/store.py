"""Vector store protocol and data types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class VectorStoreError(Exception):
    """Raised when a vector store operation fails."""


@dataclass
class PointPayload:
    """Payload stored alongside each vector point."""

    fields: dict[str, Any] = field(default_factory=dict)

    def with_field(self, key: str, value: Any) -> PointPayload:
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

    must: list[tuple[str, Any]] = field(default_factory=list)

    def must_match(self, field_name: str, value: Any) -> SearchFilter:
        """Add a must-match condition and return self for chaining."""
        self.must.append((field_name, value))
        return self


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector similarity search stores."""

    async def ensure_collection(self, collection: str, dimensions: int) -> None:
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

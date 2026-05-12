"""Store protocol and in-memory implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Store[V](Protocol):
    """Backend storage for accumulator items."""

    async def get(self, key: str) -> V | None:
        """Return the stored value for the key, if present."""

    async def set(self, key: str, value: V) -> None:
        """Store the value under the given key."""

    async def delete(self, key: str) -> None:
        """Delete the value stored for the key."""

    async def keys(self) -> list[str]:
        """Return all stored keys."""


class MemoryStore[V]:
    """In-memory dict-based Store implementation."""

    def __init__(self) -> None:
        self._data: dict[str, V] = {}

    async def get(self, key: str) -> V | None:
        return self._data.get(key)

    async def set(self, key: str, value: V) -> None:
        self._data[key] = value

    async def delete(self, key: str) -> None:
        self._data.pop(key, None)

    async def keys(self) -> list[str]:
        return list(self._data.keys())

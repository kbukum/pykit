"""Store protocol and in-memory implementation."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class Store[V](Protocol):
    """Backend storage for accumulator items."""

    async def get(self, key: str) -> V | None: ...
    async def set(self, key: str, value: V) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def keys(self) -> list[str]: ...


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

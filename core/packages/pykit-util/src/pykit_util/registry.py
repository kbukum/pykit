"""Thread-safe generic registry with asyncio lock for mutation."""

from __future__ import annotations

import asyncio
import builtins
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")


class Registry(Generic[K, V]):
    """Thread-safe typed registry.

    Reads are lock-free (safe for high-frequency lookups).
    Writes use ``asyncio.Lock`` to prevent concurrent mutation.

    Example::

        registry: Registry[str, type[Plugin]] = Registry()
        await registry.register("my_plugin", MyPlugin)
        plugin_cls = registry.get("my_plugin")
    """

    def __init__(self) -> None:
        self._store: dict[K, V] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    async def register(self, key: K, value: V) -> None:
        """Register a key-value pair. Overwrites existing entries."""
        async with self._lock:
            self._store[key] = value

    def register_sync(self, key: K, value: V) -> None:
        """Register synchronously — only safe during startup (no concurrent tasks)."""
        self._store[key] = value

    def get(self, key: K) -> V | None:
        """Return the value for ``key``, or ``None`` if not registered."""
        return self._store.get(key)

    def get_or_raise(self, key: K) -> V:
        """Return the value for ``key``, raising ``KeyError`` if not found."""
        if key not in self._store:
            raise KeyError(f"No entry registered for key: {key!r}")
        return self._store[key]

    def list(self) -> list[tuple[K, V]]:
        """Return all registered (key, value) pairs."""
        return list(self._store.items())

    def keys(self) -> builtins.list[K]:
        """Return all registered keys."""
        return list(self._store.keys())

    def values(self) -> builtins.list[V]:
        """Return all registered values."""
        return list(self._store.values())

    async def clear(self) -> None:
        """Remove all entries."""
        async with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: object) -> bool:
        return key in self._store

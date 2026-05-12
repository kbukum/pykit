"""Cache backend protocols and in-memory default implementation."""

from __future__ import annotations

import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pykit_cache.config import CacheConfig
from pykit_errors import InvalidInputError


@runtime_checkable
class CacheBackend(Protocol):
    """Async key-value cache backend contract."""

    async def get(self, key: str) -> str | None:
        raise NotImplementedError

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        raise NotImplementedError

    async def delete(self, *keys: str) -> int:
        raise NotImplementedError

    async def exists(self, *keys: str) -> int:
        raise NotImplementedError

    async def ping(self) -> bool:
        raise NotImplementedError

    async def close(self) -> None:
        raise NotImplementedError


CacheFactory = Callable[[CacheConfig], CacheBackend]


@dataclass
class _CacheEntry:
    value: str
    expires_at: float | None


class InMemoryCache:
    """Lean in-process cache backend with TTL and bounded LRU eviction."""

    def __init__(self, *, default_ttl_seconds: int | None = None, max_entries: int = 10_000) -> None:
        if default_ttl_seconds is not None and default_ttl_seconds <= 0:
            raise InvalidInputError("default_ttl_seconds must be positive", field="default_ttl_seconds")
        if max_entries <= 0:
            raise InvalidInputError("max_entries must be positive", field="max_entries")
        self._default_ttl_seconds = default_ttl_seconds
        self._max_entries = max_entries
        self._entries: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._closed = False

    async def get(self, key: str) -> str | None:
        """Return a cached value or ``None`` when missing/expired."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        if self._is_expired(entry):
            del self._entries[key]
            return None
        self._entries.move_to_end(key)
        return entry.value

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Store a value with optional Redis-compatible expiry seconds."""
        ttl = self._default_ttl_seconds if ex is None else ex
        if ttl is not None and ttl <= 0:
            raise InvalidInputError("cache TTL must be positive", field="ttl")
        expires_at = None if ttl is None else time.monotonic() + ttl
        self._entries[key] = _CacheEntry(value=value, expires_at=expires_at)
        self._entries.move_to_end(key)
        while len(self._entries) > self._max_entries:
            self._entries.popitem(last=False)

    async def delete(self, *keys: str) -> int:
        """Delete keys and return the number removed."""
        removed = 0
        for key in keys:
            if key in self._entries:
                del self._entries[key]
                removed += 1
        return removed

    async def exists(self, *keys: str) -> int:
        """Return the number of provided keys that currently exist."""
        count = 0
        for key in keys:
            if await self.get(key) is not None:
                count += 1
        return count

    async def ping(self) -> bool:
        """Return cache health."""
        return not self._closed

    async def close(self) -> None:
        """Close the backend and clear process-local state."""
        self._closed = True
        self._entries.clear()

    def _is_expired(self, entry: _CacheEntry) -> bool:
        return entry.expires_at is not None and time.monotonic() >= entry.expires_at

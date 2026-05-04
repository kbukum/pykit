"""Async cache client over an injected backend."""

from __future__ import annotations

from inspect import isawaitable
from typing import TypeVar

from pykit_cache.backends import CacheBackend
from pykit_cache.config import CacheConfig
from pykit_cache.registry import CacheRegistry, default_cache_registry
from pykit_util import JsonCodec

T = TypeVar("T")


class CacheClient:
    """Async cache client with JSON helpers."""

    def __init__(
        self,
        config: CacheConfig | None = None,
        *,
        backend: CacheBackend | None = None,
        registry: CacheRegistry | None = None,
    ) -> None:
        self._config = config or CacheConfig()
        self._backend = backend or (registry or default_cache_registry()).create(self._config)

    async def get(self, key: str) -> str | None:
        """Retrieve a value by key."""
        return await self._backend.get(key)

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Store a value with optional expiration in seconds."""
        await self._backend.set(key, value, ex=ex)

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys. Returns number of keys removed."""
        return await self._backend.delete(*keys)

    async def exists(self, *keys: str) -> int:
        """Return the number of provided keys that exist."""
        return await self._backend.exists(*keys)

    async def get_json(self, key: str, type_hint: type[T] = dict) -> T | None:  # type: ignore[assignment]
        """Get a key and JSON-decode the value."""
        _ = type_hint
        raw = await self.get(key)
        if raw is None:
            return None
        return JsonCodec[T](stringify_unknown=False).decode(raw)

    async def set_json(self, key: str, value: object, ex: int | None = None) -> None:
        """JSON-encode *value* and store it."""
        await self.set(key, JsonCodec[object](stringify_unknown=False).encode(value).decode(), ex=ex)

    async def ping(self) -> bool:
        """Return ``True`` when the backend is healthy."""
        result = self._backend.ping()
        if isawaitable(result):
            return bool(await result)
        return bool(result)

    async def close(self) -> None:
        """Close the underlying backend."""
        await self._backend.close()

    def unwrap(self) -> CacheBackend:
        """Access the underlying backend."""
        return self._backend

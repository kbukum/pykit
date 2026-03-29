"""Generic JSON-serialized typed key-value store backed by Redis."""

from __future__ import annotations

import json

from pykit_redis.client import RedisClient


class TypedStore[T]:
    """Typed, JSON-serialized key-value store with an optional key prefix."""

    def __init__(self, client: RedisClient, key_prefix: str = "") -> None:
        self._client = client
        self._prefix = key_prefix

    def _full_key(self, key: str) -> str:
        if self._prefix:
            return f"{self._prefix}:{key}"
        return key

    async def load(self, key: str) -> T | None:
        """Load and JSON-decode. Returns ``None`` if the key is missing."""
        raw = await self._client.get(self._full_key(key))
        if raw is None:
            return None
        return json.loads(raw)  # type: ignore[return-value]

    async def save(self, key: str, value: T, ttl: int | None = None) -> None:
        """JSON-encode and store with an optional TTL in seconds."""
        await self._client.set(self._full_key(key), json.dumps(value), ex=ttl)

    async def delete(self, key: str) -> None:
        """Remove the key from Redis."""
        await self._client.delete(self._full_key(key))

"""Generic JSON-serialized typed key-value store backed by cache."""

from __future__ import annotations


from pykit_util import JsonCodec
from pykit_cache.client import CacheClient


class TypedStore[T]:
    """Typed, JSON-serialized key-value store with an optional key prefix."""

    def __init__(
        self,
        client: CacheClient,
        key_prefix: str = "",
        codec: JsonCodec[T] | None = None,
    ) -> None:
        self._client = client
        self._prefix = key_prefix
        self._codec = codec or JsonCodec(stringify_unknown=False)

    def _full_key(self, key: str) -> str:
        if self._prefix:
            return f"{self._prefix}:{key}"
        return key

    async def load(self, key: str) -> T | None:
        """Load and JSON-decode. Returns ``None`` if the key is missing."""
        raw = await self._client.get(self._full_key(key))
        if raw is None:
            return None
        return self._codec.decode(raw)

    async def save(self, key: str, value: T, ttl: int | None = None) -> None:
        """JSON-encode and store with an optional TTL in seconds."""
        await self._client.set(self._full_key(key), self._codec.encode(value).decode(), ex=ttl)

    async def delete(self, key: str) -> None:
        """Remove the key from cache."""
        await self._client.delete(self._full_key(key))

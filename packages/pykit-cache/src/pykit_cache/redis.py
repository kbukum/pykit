"""Optional Redis cache adapter."""

from __future__ import annotations

from inspect import isawaitable
from typing import TYPE_CHECKING, cast

from pykit_cache.config import CacheConfig

if TYPE_CHECKING:
    from redis.asyncio import Redis

    from pykit_cache.registry import CacheRegistry


class RedisCacheBackend:
    """Redis-backed cache backend.

    Requires the ``redis`` extra and explicit ``register(registry)`` before config selection.
    """

    def __init__(self, config: CacheConfig) -> None:
        try:
            import redis.asyncio as aioredis
        except ImportError as exc:
            msg = "redis is required for RedisCacheBackend; install pykit-cache[redis]"
            raise ImportError(msg) from exc

        self._redis: Redis = aioredis.Redis.from_url(
            config.url,
            password=config.password or None,
            db=config.db,
            max_connections=config.max_connections,
            socket_timeout=config.socket_timeout,
            socket_connect_timeout=config.socket_connect_timeout,
            retry_on_timeout=config.retry_on_timeout,
            decode_responses=config.decode_responses,
        )

    async def get(self, key: str) -> str | None:
        """Retrieve a value by key."""
        return cast("str | None", await self._redis.get(key))

    async def set(self, key: str, value: str, ex: int | None = None) -> None:
        """Store a value with optional expiration in seconds."""
        await self._redis.set(key, value, ex=ex)

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys. Returns number of keys removed."""
        return cast("int", await self._redis.delete(*keys))

    async def exists(self, *keys: str) -> int:
        """Return the number of provided keys that exist."""
        return cast("int", await self._redis.exists(*keys))

    async def ping(self) -> bool:
        """Return ``True`` if the server responds to PING."""
        result = self._redis.ping()
        if isawaitable(result):
            return bool(await result)
        return bool(result)

    async def close(self) -> None:
        """Close the underlying connection pool."""
        await self._redis.aclose()

    def unwrap(self) -> Redis:
        """Access the underlying Redis client."""
        return self._redis


def register(registry: CacheRegistry) -> None:
    """Register the Redis backend in an injected registry."""
    registry.register("redis", RedisCacheBackend)

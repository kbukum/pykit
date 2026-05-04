"""Optional Redis cache adapter."""

from __future__ import annotations

import importlib
from collections.abc import Awaitable
from inspect import isawaitable
from typing import TYPE_CHECKING, Protocol, cast

from pykit_cache.config import CacheConfig
from pykit_errors import InvalidInputError

if TYPE_CHECKING:
    from pykit_cache.registry import CacheRegistry


class RedisClient(Protocol):
    """Subset of the Redis async client used by the cache adapter."""

    def get(self, key: str) -> Awaitable[object]:
        raise NotImplementedError

    def set(self, key: str, value: str, *, ex: int | None = None) -> Awaitable[object]:
        raise NotImplementedError

    def delete(self, *keys: str) -> Awaitable[object]:
        raise NotImplementedError

    def exists(self, *keys: str) -> Awaitable[object]:
        raise NotImplementedError

    def ping(self) -> Awaitable[object] | object:
        raise NotImplementedError

    def aclose(self) -> Awaitable[None]:
        raise NotImplementedError


class RedisCacheBackend:
    """Redis-backed cache backend.

    Requires the ``redis`` extra and explicit ``register(registry)`` before config selection.
    """

    def __init__(self, config: CacheConfig) -> None:
        if not config.decode_responses:
            raise InvalidInputError(
                "Redis cache backend requires decode_responses=True",
                field="decode_responses",
            )
        try:
            aioredis = importlib.import_module("redis.asyncio")
        except ImportError as exc:
            msg = "redis is required for RedisCacheBackend; install pykit-cache[redis]"
            raise ImportError(msg) from exc

        self._redis = cast(
            "RedisClient",
            aioredis.Redis.from_url(
                config.url,
                password=config.password or None,
                db=config.db,
                max_connections=config.max_connections,
                socket_timeout=config.socket_timeout,
                socket_connect_timeout=config.socket_connect_timeout,
                retry_on_timeout=config.retry_on_timeout,
                decode_responses=config.decode_responses,
            ),
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

    def unwrap(self) -> RedisClient:
        """Access the underlying Redis client."""
        return self._redis


def register(registry: CacheRegistry) -> None:
    """Register the Redis backend in an injected registry."""
    registry.register("redis", RedisCacheBackend)

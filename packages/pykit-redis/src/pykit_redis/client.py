"""Async Redis client wrapping redis.asyncio.Redis."""

from __future__ import annotations

import json
from typing import Any, TypeVar, cast

import redis.asyncio as aioredis

from pykit_redis.config import RedisConfig

T = TypeVar("T")


class RedisClient:
    """Thin async wrapper around :class:`redis.asyncio.Redis`."""

    def __init__(self, config: RedisConfig) -> None:
        self._config = config
        self._redis = aioredis.Redis.from_url(
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

    async def get_json(self, key: str, type_hint: type[T] = dict) -> T | None:  # type: ignore[assignment]
        """Get a key and JSON-decode the value."""
        raw = await self.get(key)
        if raw is None:
            return None
        return cast("T", json.loads(raw))

    async def set_json(self, key: str, value: Any, ex: int | None = None) -> None:
        """JSON-encode *value* and store it."""
        await self.set(key, json.dumps(value), ex=ex)

    async def ping(self) -> bool:
        """Return ``True`` if the server responds to PING."""
        result = self._redis.ping()
        if hasattr(result, "__await__"):
            return cast("bool", await result)
        return bool(result)

    async def close(self) -> None:
        """Close the underlying connection pool."""
        await self._redis.aclose()

    def unwrap(self) -> aioredis.Redis:
        """Access the underlying :class:`redis.asyncio.Redis` instance."""
        return self._redis

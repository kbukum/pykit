# pykit-cache-redis

Redis backend for `pykit-cache`.

## Installation

```bash
uv add pykit-cache-redis
# or
pip install pykit-cache-redis
```

## Quick start

```python
from pykit_cache import CacheConfig
from pykit_cache_redis import RedisCacheBackend

cache = RedisCacheBackend(
    CacheConfig(
        backend="redis",
        url="redis://localhost:6379/0",
        decode_responses=True,
    )
)

await cache.set("session:1", "ready", ex=300)
assert await cache.get("session:1") == "ready"
```

## Registering the backend

Use `register(registry)` when your application selects cache backends through a `CacheRegistry`.

```python
from pykit_cache import CacheConfig, CacheRegistry
from pykit_cache_redis import register as register_redis

registry = CacheRegistry()
register_redis(registry)

cache = registry.create(CacheConfig(backend="redis", url="redis://localhost:6379/0"))
```

## What this package provides

- `RedisCacheBackend` for async `get`, `set`, `delete`, `exists`, `ping`, and `close` operations.
- `register(registry)` to register the `"redis"` backend explicitly.
- `RedisClient`, a protocol describing the Redis client surface the adapter uses.

## Configuration notes

- The adapter reads Redis settings from `pykit_cache.CacheConfig`.
- `decode_responses=True` is required.
- The Redis client is imported lazily from `redis.asyncio`.
- `unwrap()` returns the underlying Redis client when you need direct access.

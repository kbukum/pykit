# pykit-redis

Async Redis client with component lifecycle, health checking, and a generic typed JSON store.

## Installation

```bash
pip install pykit-redis
# or
uv add pykit-redis
```

## Quick Start

```python
from pykit_redis import RedisConfig, RedisComponent, TypedStore

# Create and start the Redis component
config = RedisConfig(url="redis://localhost:6379/0", max_connections=20)
component = RedisComponent(config)
await component.start()

# Use the client directly
client = component.client
await client.set("key", "value", ex=300)
val = await client.get("key")  # "value"

# JSON operations
await client.set_json("user:1", {"name": "Alice", "role": "admin"})
user = await client.get_json("user:1")  # {"name": "Alice", "role": "admin"}

# Typed store with key prefix
store: TypedStore[dict] = TypedStore(client, key_prefix="sessions")
await store.save("abc", {"user_id": 42}, ttl=3600)
session = await store.load("abc")  # {"user_id": 42}

# Health check
health = await component.health()  # Health(status=HEALTHY, ...)

await component.stop()
```

## Key Components

- **RedisConfig** — Configuration dataclass (url, password, db, max_connections, timeouts, retry settings)
- **RedisClient** — Thin async wrapper around `redis.asyncio.Redis` with `get`, `set`, `delete`, `exists`, `get_json`, `set_json`, `ping`, and `unwrap()` for raw access
- **RedisComponent** — Lifecycle-managed component with `start()`, `stop()`, and `health()` (implements Component protocol)
- **TypedStore[T]** — Generic JSON-serialized key-value store with optional key prefix and TTL support

## Dependencies

- `pykit-errors`, `pykit-component`
- `redis` (redis-py async client)
- Optional: `fakeredis` (for testing)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

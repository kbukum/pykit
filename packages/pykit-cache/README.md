# pykit-cache

Async cache client with component lifecycle, health checking, and a generic typed JSON store.

## Installation

```bash
pip install pykit-cache
# or
uv add pykit-cache
```

## Quick Start

```python
from pykit_cache import CacheConfig, CacheComponent, TypedStore

# Create and start the cache component
config = CacheConfig(url="redis://localhost:6379/0", max_connections=20)
component = CacheComponent(config)
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

- **CacheConfig** — Configuration dataclass (url, password, db, max_connections, timeouts, retry settings)
- **CacheClient** — Thin async wrapper around `redis.asyncio.Redis` with `get`, `set`, `delete`, `exists`, `get_json`, `set_json`, `ping`, and `unwrap()` for raw access
- **CacheComponent** — Lifecycle-managed component with `start()`, `stop()`, and `health()` (implements Component protocol)
- **TypedStore[T]** — Generic JSON-serialized key-value store with optional key prefix and TTL support

## Dependencies

- `pykit-errors`, `pykit-component`
- `redis` (redis-py async client)
- Optional: `pykit-testutil` (for testing)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

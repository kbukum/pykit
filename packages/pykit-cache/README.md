# pykit-cache

Async cache abstraction with an in-memory lean default, explicit backend registries, component
lifecycle, and a generic typed JSON store.

## Installation

```bash
pip install pykit-cache
pip install 'pykit-cache[redis]'  # optional Redis adapter

uv add pykit-cache
uv add 'pykit-cache[redis]'  # optional Redis adapter
```

## Quick Start

```python
from pykit_cache import CacheComponent, CacheConfig, TypedStore

component = CacheComponent(CacheConfig())  # default backend="memory"
await component.start()

client = component.client
await client.set("key", "value", ex=300)
assert await client.get("key") == "value"

store: TypedStore[dict] = TypedStore(client, key_prefix="sessions")
await store.save("abc", {"user_id": 42}, ttl=3600)
```

## Explicit Redis registration

Redis is optional and is never imported or registered by the core package.

```python
from pykit_cache import CacheComponent, CacheConfig, CacheRegistry, register_memory
from pykit_cache.redis import register as register_redis

registry = CacheRegistry()
register_memory(registry)
register_redis(registry)

component = CacheComponent(
    CacheConfig(backend="redis", url="redis://localhost:6379/0"),
    registry=registry,
)
await component.start()
```

## Key Components

- **CacheConfig** — backend selection plus memory and Redis adapter settings.
- **CacheRegistry** — injected registry; a new empty registry has no backends.
- **InMemoryCache** — bounded in-process LRU cache with TTL support.
- **CacheClient** — backend-agnostic async `get`, `set`, `delete`, `exists`, JSON helpers.
- **TypedStore[T]** — JSON-serialized key-value store with optional key prefix.

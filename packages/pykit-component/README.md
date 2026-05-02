# pykit-component

Lifecycle-managed infrastructure components with protocol-based interfaces and deterministic ordering.

## Installation

```bash
pip install pykit-component
# or
uv add pykit-component
```

## Quick Start

```python
from pykit_component import Component, Health, HealthStatus, Registry

class CacheComponent:
    @property
    def name(self) -> str:
        return "cache"

    async def start(self) -> None:
        self._pool = await create_cache_pool()

    async def stop(self) -> None:
        await self._pool.close()

    async def health(self) -> Health:
        return Health(name=self.name, status=HealthStatus.HEALTHY)

# Manage multiple components with deterministic lifecycle
registry = Registry()
registry.register(CacheComponent())
registry.register(DatabaseComponent())

await registry.start_all()          # starts in registration order
statuses = await registry.health_all()
await registry.stop_all()           # stops in reverse order
```

## Key Components

- **Component** — Runtime-checkable protocol requiring `name` (property), `start()`, `stop()`, and `health()` async methods
- **Health** — Frozen dataclass with `name`, `status`, `message`, and `timestamp`
- **HealthStatus** — StrEnum: `HEALTHY`, `DEGRADED`, `UNHEALTHY`
- **Registry** — Manages component lifecycle; starts in registration order, stops in reverse; raises `ValueError` on duplicate names; collects errors during `stop_all()`
- **Describable** — Optional protocol for components that provide startup summary info via `describe() -> Description`
- **Description** — Frozen dataclass with `name`, `type`, `details`, and `port` for bootstrap display

## Dependencies

- `pykit-errors` — Error handling

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

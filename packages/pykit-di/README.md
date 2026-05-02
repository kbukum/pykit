# pykit-di

Dependency injection container with eager, lazy, and singleton registration modes.

## Installation

```bash
pip install pykit-di
# or
uv add pykit-di
```

## Quick Start

```python
from pykit_di import Container, RegistrationMode

container = Container()

# Eager: factory runs immediately at registration
container.register("config", lambda: load_config(), RegistrationMode.EAGER)

# Lazy/Singleton: factory deferred until first resolve, then cached
container.register_lazy("db", lambda: Database(container.resolve("config")))
container.register_singleton("cache", lambda: cacheCache("localhost:6379"))

# Register a pre-built instance directly
container.register_instance("logger", my_logger)

# Resolve with optional type checking
db = container.resolve("db", type_hint=Database)
db2 = container.resolve("db")  # returns same cached instance

# Introspection
container.has("db")       # True
container.names()         # ["config", "db", "cache", "logger"]
container.resolve_all()   # list of all resolved instances
```

## Key Components

- **Container** — Thread-safe DI container with registration, resolution, and circular dependency detection
- **RegistrationMode** — Enum: `EAGER` (factory runs at registration), `LAZY` (deferred + cached), `SINGLETON` (alias for LAZY)
- **register(name, factory, mode)** — Register a factory with a specific mode
- **register_instance(name, instance)** — Register a pre-built instance directly
- **register_lazy(name, factory)** / **register_singleton(name, factory)** — Shorthand registration methods
- **resolve(name, type_hint)** — Resolve by name with optional `isinstance` type checking; raises `KeyError` if not found
- **resolve_all(type_hint)** — Resolve all registered components, optionally filtered by type
- **CircularDependencyError** — Raised when circular dependencies are detected during resolution

## Dependencies

- `pykit-errors` — Error handling

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

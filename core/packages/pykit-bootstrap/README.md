# pykit-bootstrap

Async application bootstrap with lifecycle management, component integration, and signal handling.

## Installation

```bash
pip install pykit-bootstrap
# or
uv add pykit-bootstrap
```

## Quick Start

```python
import asyncio
from pykit_bootstrap import (
    App, DefaultAppConfig, ServiceConfig, Environment, Component,
)

# Configure your application
config = DefaultAppConfig(
    service=ServiceConfig(
        name="my-service",
        environment=Environment.PRODUCTION,
        version="1.0.0",
    ),
)

app = (
    App(config)
    .with_component(my_database)       # register components
    .on_configure(setup_routes)        # runs after components start
    .on_start(warm_cache)              # runs before ready check
    .on_stop(flush_metrics)            # runs in reverse order on shutdown
)

# Long-running service (waits for SIGINT/SIGTERM)
asyncio.run(app.run())

# Or run a finite task
asyncio.run(app.run_task(my_one_off_job))
```

## Key Components

- **App** — Main application with fluent API for lifecycle hooks and component registration; handles SIGINT/SIGTERM with graceful shutdown timeout
- **AppConfig** — Protocol requiring `apply_defaults()` and `service_config` property for custom config implementations
- **DefaultAppConfig** — Default `AppConfig` implementation with `ServiceConfig`, `graceful_timeout`, and convenience properties (`name`, `version`, `env`, `debug`)
- **ServiceConfig** — Frozen dataclass with `name`, `environment`, `version`, `debug`, and `LoggingConfig`
- **Environment** — StrEnum: `DEVELOPMENT`, `STAGING`, `PRODUCTION`
- **LoggingConfig** — Frozen dataclass for log `level` and `format` (`"json"` or `"console"`)
- **Lifecycle** — Manages ordered configure, start, ready, and stop hooks; stop hooks run in reverse registration order
- **Hook** — Type alias `Callable[[], Awaitable[None]]` for async lifecycle hooks
- **Registry / Component / Health / HealthStatus** — Re-exported from `pykit-component` for convenience

### Lifecycle Order

`run()`: log startup → start components → configure hooks → start hooks → ready check → ready hooks → wait for signal → stop hooks → stop components

`run_task(fn)`: log startup → start components → configure hooks → start hooks → run task → stop hooks → stop components

## Dependencies

- `pykit-component` — Component lifecycle protocol and registry
- `pykit-errors` — Error handling
- `pykit-logging` — Structured logging setup

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

"""Example: Dependency injection and application bootstrap.

Demonstrates:
- Registering services in the DI Container
- Using bootstrap App with lifecycle hooks (start / stop)
- Component Registry with ordered start and stop
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from pykit_bootstrap import App, DefaultAppConfig, Environment, ServiceConfig
from pykit_component import Health, HealthStatus, Registry
from pykit_di import Container

# ---------------------------------------------------------------------------
# 1. Dependency Injection
# ---------------------------------------------------------------------------


@dataclass
class DBConfig:
    dsn: str = "sqlite:///app.db"
    pool_size: int = 5


class UserService:
    def __init__(self, db_config: DBConfig) -> None:
        self.db_config = db_config

    def greet(self, name: str) -> str:
        return f"Hello {name}! (db={self.db_config.dsn})"


def demo_di() -> None:
    """Register and resolve services from a DI container."""
    print("=== Dependency Injection ===")
    container = Container()

    # Register a config instance directly
    container.register_instance("db_config", DBConfig(dsn="postgres://localhost/app"))

    # Register a factory that depends on the config
    container.register(
        "user_service",
        lambda: UserService(container.resolve("db_config")),
    )

    svc = container.resolve("user_service", UserService)
    print(f"  {svc.greet('Alice')}")
    print(f"  Registered: {container.names()}")

    # Lazy registration — factory runs only on first resolve
    container.register_lazy("heavy_model", lambda: {"weights": [0.1] * 1000})
    print(f"  Lazy resolved: type={type(container.resolve('heavy_model')).__name__}")


# ---------------------------------------------------------------------------
# 2. Bootstrap App with lifecycle hooks
# ---------------------------------------------------------------------------


async def demo_bootstrap() -> None:
    """Show App lifecycle: start → task → stop."""
    print("\n=== Bootstrap App ===")

    app = App(
        DefaultAppConfig(
            service=ServiceConfig(name="my-service", environment=Environment.STAGING, version="1.2.0"),
        )
    )

    async def on_start() -> None:
        print(f"  [start] {app.config.name} v{app.config.version} booting…")

    async def on_stop() -> None:
        print(f"  [stop]  {app.config.name} shutting down")

    async def main_task() -> None:
        print("  [task]  doing work…")
        await asyncio.sleep(0.05)
        print("  [task]  work done!")

    app.on_start(on_start).on_stop(on_stop)
    await app.run_task(main_task)


# ---------------------------------------------------------------------------
# 3. Component Registry — ordered start / stop
# ---------------------------------------------------------------------------


class FakeComponent:
    """Minimal Component implementation for demonstration."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        print(f"  ▶ {self._name} started")

    async def stop(self) -> None:
        print(f"  ■ {self._name} stopped")

    async def health(self) -> Health:
        return Health(name=self._name, status=HealthStatus.HEALTHY, timestamp=datetime.now(UTC))


async def demo_component_registry() -> None:
    """Components start in registration order, stop in reverse."""
    print("\n=== Component Registry ===")
    registry = Registry()

    registry.register(FakeComponent("database"))
    registry.register(FakeComponent("cache"))
    registry.register(FakeComponent("http-server"))

    print("Starting all:")
    await registry.start_all()

    healths = await registry.health_all()
    for h in healths:
        print(f"  {h.name}: {h.status}")

    print("Stopping all (reverse order):")
    await registry.stop_all()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    demo_di()
    await demo_bootstrap()
    await demo_component_registry()


if __name__ == "__main__":
    asyncio.run(main())

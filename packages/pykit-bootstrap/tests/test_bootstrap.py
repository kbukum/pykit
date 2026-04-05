"""Tests for pykit-bootstrap."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

from pykit_bootstrap import (
    App,
    AppConfig,
    Component,
    DefaultAppConfig,
    Environment,
    Health,
    HealthStatus,
    Hook,
    Lifecycle,
    LoggingConfig,
    Registry,
    ServiceConfig,
)

# ---------------------------------------------------------------------------
# Helper — shortcut for creating DefaultAppConfig
# ---------------------------------------------------------------------------


def _cfg(name: str = "svc", **kwargs: object) -> DefaultAppConfig:
    """Create a DefaultAppConfig with the given service name and optional overrides."""
    svc_kwargs: dict[str, object] = {"name": name}
    top_kwargs: dict[str, object] = {}
    svc_fields = {"name", "environment", "version", "debug", "logging"}
    for k, v in kwargs.items():
        if k in svc_fields:
            svc_kwargs[k] = v
        else:
            top_kwargs[k] = v
    return DefaultAppConfig(service=ServiceConfig(**svc_kwargs), **top_kwargs)


# ---------------------------------------------------------------------------
# Config types
# ---------------------------------------------------------------------------


class TestEnvironment:
    def test_values(self) -> None:
        assert Environment.DEVELOPMENT == "development"
        assert Environment.STAGING == "staging"
        assert Environment.PRODUCTION == "production"

    def test_str_enum(self) -> None:
        assert str(Environment.PRODUCTION) == "production"


class TestLoggingConfig:
    def test_defaults(self) -> None:
        lc = LoggingConfig()
        assert lc.level == "INFO"
        assert lc.format == "console"

    def test_frozen(self) -> None:
        lc = LoggingConfig()
        with pytest.raises(AttributeError):
            lc.level = "DEBUG"  # type: ignore[misc]


class TestServiceConfig:
    def test_defaults(self) -> None:
        sc = ServiceConfig()
        assert sc.name == ""
        assert sc.environment == Environment.DEVELOPMENT
        assert sc.version == "0.0.0"
        assert sc.debug is False
        assert isinstance(sc.logging, LoggingConfig)

    def test_custom_values(self) -> None:
        sc = ServiceConfig(
            name="api",
            environment=Environment.PRODUCTION,
            version="1.2.3",
            debug=True,
            logging=LoggingConfig(level="DEBUG", format="json"),
        )
        assert sc.name == "api"
        assert sc.environment == Environment.PRODUCTION
        assert sc.version == "1.2.3"
        assert sc.debug is True
        assert sc.logging.level == "DEBUG"
        assert sc.logging.format == "json"

    def test_frozen(self) -> None:
        sc = ServiceConfig(name="x")
        with pytest.raises(AttributeError):
            sc.name = "y"  # type: ignore[misc]


class TestDefaultAppConfig:
    def test_defaults(self) -> None:
        cfg = DefaultAppConfig()
        assert cfg.service.name == ""
        assert cfg.service.environment == Environment.DEVELOPMENT
        assert cfg.graceful_timeout == 30.0

    def test_convenience_properties(self) -> None:
        cfg = _cfg("svc", version="2.0", environment=Environment.STAGING, debug=True)
        assert cfg.name == "svc"
        assert cfg.version == "2.0"
        assert cfg.env == "staging"
        assert cfg.debug is True

    def test_service_config_property(self) -> None:
        sc = ServiceConfig(name="x")
        cfg = DefaultAppConfig(service=sc)
        assert cfg.service_config is sc

    def test_apply_defaults_fills_empty_name(self) -> None:
        cfg = DefaultAppConfig()
        cfg.apply_defaults()
        assert cfg.service.name == "unknown"

    def test_apply_defaults_preserves_existing_name(self) -> None:
        cfg = _cfg("real-svc")
        cfg.apply_defaults()
        assert cfg.service.name == "real-svc"

    def test_satisfies_protocol(self) -> None:
        cfg = _cfg("proto-test")
        assert isinstance(cfg, AppConfig)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    async def test_start_hooks_run_in_order(self) -> None:
        order: list[int] = []
        lc = Lifecycle()
        lc.on_start(self._hook(order, 1))
        lc.on_start(self._hook(order, 2))
        lc.on_start(self._hook(order, 3))
        await lc.run_start_hooks()
        assert order == [1, 2, 3]

    async def test_ready_hooks_run_in_order(self) -> None:
        order: list[int] = []
        lc = Lifecycle()
        lc.on_ready(self._hook(order, 10))
        lc.on_ready(self._hook(order, 20))
        await lc.run_ready_hooks()
        assert order == [10, 20]

    async def test_stop_hooks_run_in_reverse(self) -> None:
        order: list[int] = []
        lc = Lifecycle()
        lc.on_stop(self._hook(order, 1))
        lc.on_stop(self._hook(order, 2))
        lc.on_stop(self._hook(order, 3))
        await lc.run_stop_hooks()
        assert order == [3, 2, 1]

    async def test_configure_hooks_run_in_order(self) -> None:
        order: list[int] = []
        lc = Lifecycle()
        lc.on_configure(self._hook(order, 1))
        lc.on_configure(self._hook(order, 2))
        lc.on_configure(self._hook(order, 3))
        await lc.run_configure_hooks()
        assert order == [1, 2, 3]

    async def test_no_hooks_is_noop(self) -> None:
        lc = Lifecycle()
        await lc.run_configure_hooks()
        await lc.run_start_hooks()
        await lc.run_ready_hooks()
        await lc.run_stop_hooks()

    async def test_hook_error_propagates(self) -> None:
        lc = Lifecycle()

        async def failing() -> None:
            raise RuntimeError("boom")

        lc.on_start(failing)
        with pytest.raises(RuntimeError, match="boom"):
            await lc.run_start_hooks()

    # helper
    @staticmethod
    def _hook(order: list[int], value: int) -> Hook:
        async def _h() -> None:
            order.append(value)

        return _h


# ---------------------------------------------------------------------------
# App — chaining API
# ---------------------------------------------------------------------------


class TestAppChaining:
    def test_convenience_methods_return_self(self) -> None:
        app = App(_cfg("svc"))
        sentinel = AsyncMock()
        result = (
            app.on_configure(sentinel)
            .on_start(sentinel)
            .on_ready(sentinel)
            .on_stop(sentinel)
            .set_ready_check(sentinel)
        )
        assert result is app

    def test_with_component_returns_self(self) -> None:
        app = App(_cfg("svc"))
        comp = _MockComponent("db")
        result = app.with_component(comp)
        assert result is app


# ---------------------------------------------------------------------------
# App.run_task
# ---------------------------------------------------------------------------


class TestRunTask:
    async def test_task_runs_between_hooks(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.on_start(_make_hook(order, "start"))
        app.on_stop(_make_hook(order, "stop"))

        async def task() -> None:
            order.append("task")

        await app.run_task(task)
        assert order == ["start", "task", "stop"]

    async def test_stop_hooks_run_even_if_task_fails(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.on_stop(_make_hook(order, "stop"))

        async def failing_task() -> None:
            raise ValueError("task error")

        with pytest.raises(ValueError, match="task error"):
            await app.run_task(failing_task)

        assert "stop" in order

    async def test_stop_hooks_run_even_if_start_hook_fails(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))

        async def bad_start() -> None:
            raise RuntimeError("start failed")

        app.on_start(bad_start)
        app.on_stop(_make_hook(order, "stop"))

        with pytest.raises(RuntimeError, match="start failed"):
            await app.run_task(AsyncMock())

        assert "stop" in order


# ---------------------------------------------------------------------------
# App.run (mocked signal wait)
# ---------------------------------------------------------------------------


class TestRun:
    async def test_full_lifecycle_order(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.on_start(_make_hook(order, "start"))
        app.on_ready(_make_hook(order, "ready"))
        app.on_stop(_make_hook(order, "stop"))

        async def ready_check() -> None:
            order.append("check")

        app.set_ready_check(ready_check)

        with patch.object(app, "_wait_for_signal", new_callable=AsyncMock):
            await app.run()

        assert order == ["start", "check", "ready", "stop"]

    async def test_ready_check_failure_skips_ready_hooks(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.on_start(_make_hook(order, "start"))
        app.on_ready(_make_hook(order, "ready"))
        app.on_stop(_make_hook(order, "stop"))

        async def failing_check() -> None:
            raise RuntimeError("not ready")

        app.set_ready_check(failing_check)

        with (
            patch.object(app, "_wait_for_signal", new_callable=AsyncMock),
            pytest.raises(RuntimeError, match="not ready"),
        ):
            await app.run()

        assert "start" in order
        assert "ready" not in order
        assert "stop" in order

    async def test_no_ready_check_skips_check(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.on_start(_make_hook(order, "start"))
        app.on_ready(_make_hook(order, "ready"))
        app.on_stop(_make_hook(order, "stop"))

        with patch.object(app, "_wait_for_signal", new_callable=AsyncMock):
            await app.run()

        assert order == ["start", "ready", "stop"]


# ---------------------------------------------------------------------------
# App — config / lifecycle properties
# ---------------------------------------------------------------------------


class TestAppProperties:
    def test_config_property(self) -> None:
        cfg = _cfg("svc", version="2.0")
        app = App(cfg)
        assert app.config is cfg

    def test_lifecycle_property(self) -> None:
        app = App(_cfg("svc"))
        assert isinstance(app.lifecycle, Lifecycle)


# ---------------------------------------------------------------------------
# App — signal handling & shutdown
# ---------------------------------------------------------------------------


class TestSignalHandling:
    async def test_wait_for_signal_registers_and_removes_handlers(self) -> None:
        """Cover _wait_for_signal sets/removes signal handlers."""
        import signal

        app = App(_cfg("sig-test"))

        async def fire_signal_soon() -> None:
            await asyncio.sleep(0.01)
            loop = asyncio.get_running_loop()
            loop.call_soon(lambda: os.kill(os.getpid(), signal.SIGINT))

        task = asyncio.create_task(fire_signal_soon())
        await app._wait_for_signal()
        await task

    async def test_run_registers_signal_and_completes(self) -> None:
        """Full run() with a real signal delivery — covers the signal path."""
        import signal

        order: list[str] = []
        app = App(_cfg("full-sig"))
        app.on_start(_make_hook(order, "start"))
        app.on_ready(_make_hook(order, "ready"))
        app.on_stop(_make_hook(order, "stop"))

        async def send_sigint() -> None:
            await asyncio.sleep(0.02)
            os.kill(os.getpid(), signal.SIGINT)

        task = asyncio.create_task(send_sigint())
        await app.run()
        await task
        assert order == ["start", "ready", "stop"]

    async def test_shutdown_timeout(self) -> None:
        """Cover graceful shutdown timeout path."""
        app = App(_cfg("timeout-test"), graceful_timeout=0.01)

        async def slow_stop() -> None:
            await asyncio.sleep(10)

        app.on_stop(slow_stop)

        with patch.object(app, "_wait_for_signal", new_callable=AsyncMock):
            await app.run()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hook(order: list[str], label: str) -> Hook:
    async def _h() -> None:
        order.append(label)

    return _h


# ---------------------------------------------------------------------------
# Mock component for integration tests
# ---------------------------------------------------------------------------


class _MockComponent:
    """Minimal Component implementation for testing."""

    def __init__(self, name: str, *, order: list[str] | None = None) -> None:
        self._name = name
        self._order = order
        self._started = False

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        self._started = True
        if self._order is not None:
            self._order.append(f"{self._name}:start")

    async def stop(self) -> None:
        self._started = False
        if self._order is not None:
            self._order.append(f"{self._name}:stop")

    async def health(self) -> Health:
        status = HealthStatus.HEALTHY if self._started else HealthStatus.UNHEALTHY
        return Health(name=self._name, status=status)


# ---------------------------------------------------------------------------
# App — component integration
# ---------------------------------------------------------------------------


class TestAppComponents:
    def test_with_component_registers(self) -> None:
        app = App(_cfg("svc"))
        comp = _MockComponent("db")
        app.with_component(comp)
        assert app.registry.get("db") is comp

    def test_registry_property(self) -> None:
        app = App(_cfg("svc"))
        assert isinstance(app.registry, Registry)

    async def test_components_start_before_hooks(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.with_component(_MockComponent("db", order=order))
        app.on_configure(_make_hook(order, "configure"))
        app.on_start(_make_hook(order, "start"))
        app.on_stop(_make_hook(order, "stop"))

        async def task() -> None:
            order.append("task")

        await app.run_task(task)
        assert order == ["db:start", "configure", "start", "task", "stop", "db:stop"]

    async def test_full_lifecycle_with_components(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.with_component(_MockComponent("db", order=order))
        app.on_configure(_make_hook(order, "configure"))
        app.on_start(_make_hook(order, "start"))
        app.on_ready(_make_hook(order, "ready"))
        app.on_stop(_make_hook(order, "stop"))

        with patch.object(app, "_wait_for_signal", new_callable=AsyncMock):
            await app.run()

        assert order == ["db:start", "configure", "start", "ready", "stop", "db:stop"]

    async def test_components_stop_even_on_hook_failure(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.with_component(_MockComponent("db", order=order))

        async def bad_start() -> None:
            raise RuntimeError("hook failed")

        app.on_start(bad_start)

        with pytest.raises(RuntimeError, match="hook failed"):
            await app.run_task(AsyncMock())

        assert "db:start" in order
        assert "db:stop" in order

    async def test_components_stop_in_reverse_order(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.with_component(_MockComponent("db", order=order))
        app.with_component(_MockComponent("cache", order=order))

        async def task() -> None:
            pass

        await app.run_task(task)
        assert order == ["db:start", "cache:start", "cache:stop", "db:stop"]

    async def test_shutdown_stops_components_after_timeout(self) -> None:
        order: list[str] = []
        app = App(_cfg("timeout-test"), graceful_timeout=0.01)
        app.with_component(_MockComponent("db", order=order))

        async def slow_stop() -> None:
            await asyncio.sleep(10)

        app.on_stop(slow_stop)

        with patch.object(app, "_wait_for_signal", new_callable=AsyncMock):
            await app.run()

        # Components should still be stopped even after hook timeout
        assert "db:start" in order
        assert "db:stop" in order


# ---------------------------------------------------------------------------
# Re-exports
# ---------------------------------------------------------------------------


class TestReExports:
    def test_component_reexported(self) -> None:
        assert Component is not None

    def test_health_reexported(self) -> None:
        assert Health is not None

    def test_health_status_reexported(self) -> None:
        assert HealthStatus is not None

    def test_registry_reexported(self) -> None:
        assert Registry is not None

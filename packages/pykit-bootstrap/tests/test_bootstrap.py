"""Tests for pykit-bootstrap."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, patch

import pytest

from pykit_bootstrap import (
    EVENT_READY,
    EVENT_START,
    EVENT_STOP,
    App,
    AppConfig,
    Component,
    DefaultAppConfig,
    Environment,
    Health,
    HealthStatus,
    Hook,
    Lifecycle,
    LifecycleEvent,
    LoggingConfig,
    Registry,
    ServiceConfig,
)


@dataclass(slots=True)
class _LoggerStub:
    infos: list[tuple[str, dict[str, object]]]
    errors: list[tuple[str, dict[str, object]]]

    def info(self, event: str, /, **kwargs: object) -> None:
        self.infos.append((event, kwargs))

    def error(self, event: str, /, **kwargs: object) -> None:
        self.errors.append((event, kwargs))


class _MockComponent:
    """Minimal component implementation for tests."""

    def __init__(
        self,
        name: str,
        *,
        order: list[str] | None = None,
        start_error: Exception | None = None,
        stop_error: Exception | None = None,
    ) -> None:
        self._name = name
        self._order = order
        self._start_error = start_error
        self._stop_error = stop_error
        self._started = False

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        if self._order is not None:
            self._order.append(f"{self._name}:start")
        if self._start_error is not None:
            raise self._start_error
        self._started = True

    async def stop(self) -> None:
        if self._order is not None:
            self._order.append(f"{self._name}:stop")
        if self._stop_error is not None:
            raise self._stop_error
        self._started = False

    async def health(self) -> Health:
        status = HealthStatus.HEALTHY if self._started else HealthStatus.UNHEALTHY
        return Health(name=self._name, status=status)


def _cfg(name: str = "svc", **kwargs: object) -> DefaultAppConfig:
    """Create a DefaultAppConfig with top-level convenience overrides."""
    svc_kwargs: dict[str, object] = {"name": name}
    top_kwargs: dict[str, object] = {}
    svc_fields = {"name", "environment", "version", "debug", "logging"}
    for key, value in kwargs.items():
        if key in svc_fields:
            svc_kwargs[key] = value
        else:
            top_kwargs[key] = value
    return DefaultAppConfig(service=ServiceConfig(**svc_kwargs), **top_kwargs)


def _make_hook(order: list[str], label: str) -> Hook:
    async def _hook() -> None:
        order.append(label)

    return _hook


class TestConfigTypes:
    def test_environment_values(self) -> None:
        assert Environment.DEVELOPMENT == "development"
        assert Environment.STAGING == "staging"
        assert Environment.PRODUCTION == "production"

    def test_logging_config_defaults(self) -> None:
        cfg = LoggingConfig()
        assert cfg.level == "INFO"
        assert cfg.format == "console"

    def test_service_config_defaults(self) -> None:
        cfg = ServiceConfig()
        assert cfg.name == ""
        assert cfg.environment == Environment.DEVELOPMENT
        assert cfg.version == "0.0.0"
        assert cfg.debug is False

    def test_default_app_config_protocol(self) -> None:
        cfg = _cfg("svc", version="1.2.3")
        assert isinstance(cfg, AppConfig)
        assert cfg.service_config.name == "svc"
        assert cfg.version == "1.2.3"


class TestLifecycle:
    async def test_start_hooks_run_in_order(self) -> None:
        order: list[int] = []
        lifecycle = Lifecycle()
        lifecycle.on_start(self._hook(order, 1))
        lifecycle.on_start(self._hook(order, 2))
        lifecycle.on_start(self._hook(order, 3))

        await lifecycle.run_start_hooks(app_name="svc")

        assert order == [1, 2, 3]

    async def test_stop_hooks_run_in_reverse_order(self) -> None:
        order: list[int] = []
        lifecycle = Lifecycle()
        lifecycle.on_stop(self._hook(order, 1))
        lifecycle.on_stop(self._hook(order, 2))
        lifecycle.on_stop(self._hook(order, 3))

        await lifecycle.run_stop_hooks(app_name="svc")

        assert order == [3, 2, 1]

    async def test_context_and_event_are_forwarded(self) -> None:
        seen: list[tuple[dict[str, object] | None, LifecycleEvent]] = []
        lifecycle = Lifecycle()

        async def handler(context: dict[str, object] | None, event: LifecycleEvent) -> None:
            seen.append((context, event))

        lifecycle.on_ready(handler)
        await lifecycle.run_ready_hooks(app_name="svc", context={"phase": "ready"})

        context, event = seen[0]
        assert context == {"phase": "ready"}
        assert event.type == EVENT_READY
        assert event.app_name == "svc"

    async def test_hook_error_runs_later_handlers_and_raises(self) -> None:
        order: list[str] = []
        lifecycle = Lifecycle()

        async def failing() -> None:
            order.append("failing")
            raise RuntimeError("boom")

        lifecycle.on_start(failing)
        lifecycle.on_start(_make_hook(order, "after"))

        with pytest.raises(RuntimeError, match="boom"):
            await lifecycle.run_start_hooks(app_name="svc")

        assert order == ["failing", "after"]

    @staticmethod
    def _hook(order: list[int], value: int) -> Hook:
        async def _hook() -> None:
            order.append(value)

        return _hook


class TestAppAPI:
    def test_chaining_returns_self(self) -> None:
        app = App(_cfg("svc"))
        result = (
            app.on_configure(AsyncMock())
            .on_start(AsyncMock())
            .on_ready(AsyncMock())
            .on_stop(AsyncMock())
            .set_ready_check(AsyncMock())
        )
        assert result is app

    def test_with_component_returns_self(self) -> None:
        app = App(_cfg("svc"))
        component = _MockComponent("db")
        assert app.with_component(component) is app
        assert app.registry.get("db") is component

    def test_properties_expose_config_lifecycle_and_registry(self) -> None:
        app = App(_cfg("svc"))
        assert app.config.service_config.name == "svc"
        assert isinstance(app.lifecycle, Lifecycle)
        assert isinstance(app.registry, Registry)


class TestRunTask:
    async def test_run_task_orders_configure_start_task_stop(self) -> None:
        order: list[str] = []
        app = App(_cfg("svc"))
        app.with_component(_MockComponent("db", order=order))
        app.on_configure(_make_hook(order, "configure"))
        app.on_start(_make_hook(order, "on_start"))
        app.on_stop(_make_hook(order, "on_stop"))

        async def task() -> None:
            order.append("task")

        await app.run_task(task)

        assert order == ["configure", "db:start", "on_start", "task", "on_stop", "db:stop"]

    async def test_run_task_start_hook_failure_still_runs_stop_hooks(self) -> None:
        order: list[str] = []
        app = App(_cfg("svc"))
        app.with_component(_MockComponent("db", order=order))
        app.on_stop(_make_hook(order, "on_stop"))

        async def bad_start() -> None:
            order.append("on_start")
            raise RuntimeError("start failed")

        app.on_start(bad_start)

        with pytest.raises(RuntimeError, match="start failed"):
            await app.run_task(AsyncMock())

        assert order == ["db:start", "on_start", "on_stop", "db:stop"]

    async def test_logger_can_be_injected(self) -> None:
        logger = _LoggerStub([], [])
        app = App(_cfg("svc"), logger=logger)

        await app.run_task(AsyncMock())

        assert any(event == "Starting application" for event, _ in logger.infos)
        assert any(event == "Shutting down" for event, _ in logger.infos)


class TestRun:
    async def test_full_lifecycle_order_matches_bootstrap_contract(self) -> None:
        order: list[str] = []
        app = App(_cfg("svc"))
        app.with_component(_MockComponent("db", order=order))
        app.on_configure(_make_hook(order, "configure"))
        app.on_start(_make_hook(order, "on_start"))
        app.on_ready(_make_hook(order, "on_ready"))
        app.on_stop(_make_hook(order, "on_stop"))

        async def ready_check() -> None:
            order.append("ready_check")

        app.set_ready_check(ready_check)

        with patch.object(app, "_wait_for_signal", new_callable=AsyncMock):
            await app.run()

        assert order == [
            "configure",
            "db:start",
            "on_start",
            "ready_check",
            "on_ready",
            "on_stop",
            "db:stop",
        ]

    async def test_lifecycle_events_use_public_event_types(self) -> None:
        events: list[str] = []
        app = App(_cfg("svc"))

        async def on_start(event: LifecycleEvent) -> None:
            events.append(event.type)

        async def on_ready(event: LifecycleEvent) -> None:
            events.append(event.type)

        async def on_stop(event: LifecycleEvent) -> None:
            events.append(event.type)

        app.on_start(on_start)
        app.on_ready(on_ready)
        app.on_stop(on_stop)

        with patch.object(app, "_wait_for_signal", new_callable=AsyncMock):
            await app.run()

        assert events == [EVENT_START, EVENT_READY, EVENT_STOP]


class TestReExports:
    def test_component_reexported(self) -> None:
        assert Component is not None

    def test_registry_reexported(self) -> None:
        assert Registry is not None

    def test_lifecycle_event_reexported(self) -> None:
        assert LifecycleEvent(type=EVENT_START, app_name="svc") is not None

    def test_health_types_reexported(self) -> None:
        assert Health is not None
        assert HealthStatus is not None
        assert EVENT_STOP == "lifecycle.stop"

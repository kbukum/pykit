"""Extended tests for pykit-bootstrap."""

from __future__ import annotations

import asyncio
import os
import signal
from unittest.mock import AsyncMock, patch

import pytest

from pykit_bootstrap import (
    App,
    DefaultAppConfig,
    Health,
    HealthStatus,
    Lifecycle,
    LifecycleEvent,
    ServiceConfig,
)


class _MockComponent:
    """Minimal component implementation for tests."""

    def __init__(
        self,
        name: str,
        *,
        order: list[str] | None = None,
        start_error: Exception | None = None,
        stop_error: Exception | None = None,
        health_status: HealthStatus = HealthStatus.HEALTHY,
    ) -> None:
        self._name = name
        self._order = order
        self._start_error = start_error
        self._stop_error = stop_error
        self._health_status = health_status
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
        status = self._health_status if self._started else HealthStatus.UNHEALTHY
        return Health(name=self._name, status=status)


def _cfg(name: str = "svc", **kwargs: object) -> DefaultAppConfig:
    svc_kwargs: dict[str, object] = {"name": name}
    top_kwargs: dict[str, object] = {}
    svc_fields = {"name", "environment", "version", "debug", "logging"}
    for key, value in kwargs.items():
        if key in svc_fields:
            svc_kwargs[key] = value
        else:
            top_kwargs[key] = value
    return DefaultAppConfig(service=ServiceConfig(**svc_kwargs), **top_kwargs)


def _make_hook(order: list[str], label: str):
    async def _hook() -> None:
        order.append(label)

    return _hook


class TestStartupFailures:
    async def test_component_start_failure_emits_stop_hooks(self) -> None:
        order: list[str] = []
        app = App(_cfg("svc"))
        app.on_configure(_make_hook(order, "configure"))
        app.on_stop(_make_hook(order, "on_stop"))
        app.with_component(_MockComponent("db", order=order))
        app.with_component(_MockComponent("cache", order=order, start_error=RuntimeError("cache boom")))

        with pytest.raises(RuntimeError, match="cache boom"):
            await app.run_task(AsyncMock())

        assert order == ["configure", "db:start", "cache:start", "db:stop", "on_stop"]

    async def test_ready_check_failure_runs_stop_hooks_before_components_stop(self) -> None:
        order: list[str] = []
        app = App(_cfg("svc"))
        app.with_component(_MockComponent("db", order=order))
        app.on_stop(_make_hook(order, "on_stop"))

        async def failing_ready_check() -> None:
            order.append("ready_check")
            raise RuntimeError("not ready")

        app.set_ready_check(failing_ready_check)

        with (
            patch.object(app, "_wait_for_signal", new_callable=AsyncMock),
            pytest.raises(RuntimeError, match="not ready"),
        ):
            await app.run()

        assert order == ["db:start", "ready_check", "on_stop", "db:stop"]

    async def test_task_exception_wins_over_shutdown_timeout(self) -> None:
        app = App(_cfg("svc"), graceful_timeout=0.01)

        async def slow_stop() -> None:
            await asyncio.sleep(10)

        app.on_stop(slow_stop)

        async def failing_task() -> None:
            raise ValueError("task boom")

        with pytest.raises(ValueError, match="task boom"):
            await app.run_task(failing_task)


class TestHookHandling:
    async def test_stop_hook_error_does_not_prevent_component_stop(self) -> None:
        order: list[str] = []
        app = App(_cfg("svc"))
        app.with_component(_MockComponent("db", order=order))

        async def failing_stop() -> None:
            order.append("failing_stop")
            raise RuntimeError("stop hook failed")

        app.on_stop(failing_stop)
        app.on_stop(_make_hook(order, "after_stop"))

        with (
            patch.object(app, "_wait_for_signal", new_callable=AsyncMock),
            pytest.raises(RuntimeError, match="stop hook failed"),
        ):
            await app.run()

        assert order == ["db:start", "after_stop", "failing_stop", "db:stop"]

    async def test_lifecycle_context_handlers_receive_app_context(self) -> None:
        seen: list[tuple[dict[str, object] | None, LifecycleEvent]] = []
        app = App(_cfg("svc"))

        async def on_start(context: dict[str, object] | None, event: LifecycleEvent) -> None:
            seen.append((context, event))

        app.on_start(on_start)
        await app.run_task(AsyncMock())

        context, event = seen[0]
        assert context is not None
        assert context["app"] is app
        assert context["registry"] is app.registry
        assert event.app_name == "svc"

    async def test_lifecycle_preserves_cancelled_error(self) -> None:
        lifecycle = Lifecycle()

        async def cancelling() -> None:
            raise asyncio.CancelledError()

        lifecycle.on_start(cancelling)
        with pytest.raises(asyncio.CancelledError):
            await lifecycle.run_start_hooks(app_name="svc")


class TestSignalHandling:
    async def test_wait_for_signal_registers_and_removes_handlers(self) -> None:
        app = App(_cfg("sig"))

        async def fire_signal() -> None:
            await asyncio.sleep(0.01)
            os.kill(os.getpid(), signal.SIGINT)

        task = asyncio.create_task(fire_signal())
        await app._wait_for_signal()
        await task

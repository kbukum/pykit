"""Tests for pykit-bootstrap."""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, patch

import pytest

from pykit_bootstrap import App, AppConfig, Hook, Lifecycle

# ---------------------------------------------------------------------------
# AppConfig
# ---------------------------------------------------------------------------


class TestAppConfig:
    def test_defaults(self) -> None:
        cfg = AppConfig(name="svc")
        assert cfg.name == "svc"
        assert cfg.version == "dev"
        assert cfg.env == "development"
        assert cfg.debug is False
        assert cfg.graceful_timeout == 30.0
        assert cfg.extra == {}

    def test_custom_values(self) -> None:
        cfg = AppConfig(
            name="api",
            version="1.2.3",
            env="production",
            debug=True,
            graceful_timeout=10.0,
            extra={"region": "us-east-1"},
        )
        assert cfg.name == "api"
        assert cfg.version == "1.2.3"
        assert cfg.env == "production"
        assert cfg.debug is True
        assert cfg.graceful_timeout == 10.0
        assert cfg.extra == {"region": "us-east-1"}


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

    async def test_no_hooks_is_noop(self) -> None:
        lc = Lifecycle()
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
        app = App(AppConfig(name="svc"))
        sentinel = AsyncMock()
        result = app.on_start(sentinel).on_ready(sentinel).on_stop(sentinel).set_ready_check(sentinel)
        assert result is app


# ---------------------------------------------------------------------------
# App.run_task
# ---------------------------------------------------------------------------


class TestRunTask:
    async def test_task_runs_between_hooks(self) -> None:
        order: list[str] = []
        app = App(AppConfig(name="test"))
        app.on_start(_make_hook(order, "start"))
        app.on_stop(_make_hook(order, "stop"))

        async def task() -> None:
            order.append("task")

        await app.run_task(task)
        assert order == ["start", "task", "stop"]

    async def test_stop_hooks_run_even_if_task_fails(self) -> None:
        order: list[str] = []
        app = App(AppConfig(name="test"))
        app.on_stop(_make_hook(order, "stop"))

        async def failing_task() -> None:
            raise ValueError("task error")

        with pytest.raises(ValueError, match="task error"):
            await app.run_task(failing_task)

        assert "stop" in order

    async def test_stop_hooks_run_even_if_start_hook_fails(self) -> None:
        order: list[str] = []
        app = App(AppConfig(name="test"))

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
        app = App(AppConfig(name="test"))
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
        app = App(AppConfig(name="test"))
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
        app = App(AppConfig(name="test"))
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
        cfg = AppConfig(name="svc", version="2.0")
        app = App(cfg)
        assert app.config is cfg

    def test_lifecycle_property(self) -> None:
        app = App(AppConfig(name="svc"))
        assert isinstance(app.lifecycle, Lifecycle)


# ---------------------------------------------------------------------------
# App — signal handling & shutdown
# ---------------------------------------------------------------------------


class TestSignalHandling:
    async def test_wait_for_signal_registers_and_removes_handlers(self) -> None:
        """Cover lines 108-119: _wait_for_signal sets/removes signal handlers."""
        import signal

        app = App(AppConfig(name="sig-test"))

        async def fire_signal_soon() -> None:
            await asyncio.sleep(0.01)
            loop = asyncio.get_running_loop()
            # Simulate SIGINT being delivered
            loop.call_soon(lambda: os.kill(os.getpid(), signal.SIGINT))

        task = asyncio.create_task(fire_signal_soon())
        await app._wait_for_signal()
        await task

    async def test_run_registers_signal_and_completes(self) -> None:
        """Full run() with a real signal delivery — covers the signal path."""
        import signal

        order: list[str] = []
        app = App(AppConfig(name="full-sig"))
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
        """Cover lines 128-129: graceful shutdown timeout path."""
        app = App(AppConfig(name="timeout-test", graceful_timeout=0.01))

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

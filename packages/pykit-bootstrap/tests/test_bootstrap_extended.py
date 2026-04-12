"""Extended tests for pykit-bootstrap — covering edge cases and gap areas."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from pykit_bootstrap import (
    App,
    AppConfig,
    DefaultAppConfig,
    Environment,
    Health,
    HealthStatus,
    Lifecycle,
    LoggingConfig,
    ServiceConfig,
)
from pykit_component import Registry

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


def _make_hook(order: list[str], label: str):
    async def _h() -> None:
        order.append(label)

    return _h


class _MockComponent:
    """Minimal Component implementation for testing."""

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
        self._started = False
        self._start_error = start_error
        self._stop_error = stop_error
        self._health_status = health_status

    @property
    def name(self) -> str:
        return self._name

    async def start(self) -> None:
        if self._order is not None:
            self._order.append(f"{self._name}:start")
        if self._start_error:
            raise self._start_error
        self._started = True

    async def stop(self) -> None:
        if self._order is not None:
            self._order.append(f"{self._name}:stop")
        if self._stop_error:
            raise self._stop_error
        self._started = False

    async def health(self) -> Health:
        status = self._health_status if self._started else HealthStatus.UNHEALTHY
        return Health(name=self._name, status=status)


# ---------------------------------------------------------------------------
# 1. Async hook cancellation (CancelledError)
# ---------------------------------------------------------------------------


class TestAsyncHookCancellation:
    async def test_cancelled_start_hook_propagates(self) -> None:
        lc = Lifecycle()

        async def cancelling_hook() -> None:
            raise asyncio.CancelledError()

        lc.on_start(cancelling_hook)
        with pytest.raises(asyncio.CancelledError):
            await lc.run_start_hooks()

    async def test_cancelled_configure_hook_propagates(self) -> None:
        lc = Lifecycle()

        async def cancelling_hook() -> None:
            raise asyncio.CancelledError()

        lc.on_configure(cancelling_hook)
        with pytest.raises(asyncio.CancelledError):
            await lc.run_configure_hooks()

    async def test_cancelled_stop_hook_propagates(self) -> None:
        lc = Lifecycle()

        async def cancelling_hook() -> None:
            raise asyncio.CancelledError()

        lc.on_stop(cancelling_hook)
        with pytest.raises(asyncio.CancelledError):
            await lc.run_stop_hooks()


# ---------------------------------------------------------------------------
# 2. Concurrent hook failures in run_stop_hooks (error aggregation)
# ---------------------------------------------------------------------------


class TestStopHookErrors:
    async def test_first_stop_hook_error_propagates(self) -> None:
        """Stop hooks run sequentially (reversed), first error propagates."""
        lc = Lifecycle()
        order: list[str] = []

        async def hook_a() -> None:
            order.append("a")

        async def hook_b() -> None:
            order.append("b")
            raise RuntimeError("b failed")

        # Registration order: a, b → stop order: b, a
        lc.on_stop(hook_a)
        lc.on_stop(hook_b)

        with pytest.raises(RuntimeError, match="b failed"):
            await lc.run_stop_hooks()

        # b runs first (reversed), fails, a never runs
        assert order == ["b"]

    async def test_stop_hook_error_does_not_prevent_component_stop(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.with_component(_MockComponent("db", order=order))

        async def failing_stop() -> None:
            raise RuntimeError("hook error")

        app.on_stop(failing_stop)

        with patch.object(app, "_wait_for_signal", new_callable=AsyncMock), pytest.raises(RuntimeError, match="hook error"):
                await app.run()

        # Components should still stop (via finally) even after hook error
        assert "db:start" in order
        assert "db:stop" in order


# ---------------------------------------------------------------------------
# 3. RunTask with exception + graceful shutdown race
# ---------------------------------------------------------------------------


class TestRunTaskExceptionShutdown:
    async def test_task_exception_triggers_shutdown(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        app.with_component(_MockComponent("db", order=order))
        app.on_stop(_make_hook(order, "stop"))

        async def failing_task() -> None:
            raise ValueError("task boom")

        with pytest.raises(ValueError, match="task boom"):
            await app.run_task(failing_task)

        assert "stop" in order
        assert "db:stop" in order

    async def test_task_exception_with_stop_hook_error(self) -> None:
        """When both task and stop hook fail, task exception wins."""
        app = App(_cfg("test"), graceful_timeout=0.01)

        async def slow_stop() -> None:
            await asyncio.sleep(10)

        app.on_stop(slow_stop)

        async def failing_task() -> None:
            raise ValueError("task error")

        # The task error should propagate; stop hook times out
        with pytest.raises(ValueError, match="task error"):
            await app.run_task(failing_task)


# ---------------------------------------------------------------------------
# 4. Ready check timeout
# ---------------------------------------------------------------------------


class TestReadyCheckTimeout:
    async def test_slow_ready_check_blocks_startup(self) -> None:
        """Ready check that takes too long should propagate naturally."""
        app = App(_cfg("test"))

        async def slow_check() -> None:
            await asyncio.sleep(0.05)

        app.set_ready_check(slow_check)

        with patch.object(app, "_wait_for_signal", new_callable=AsyncMock):
            # Should still complete — just slowly
            await app.run()

    async def test_failing_ready_check_propagates(self) -> None:
        app = App(_cfg("test"))

        async def failing_check() -> None:
            raise RuntimeError("health check failed")

        app.set_ready_check(failing_check)
        order: list[str] = []
        app.on_stop(_make_hook(order, "stop"))

        with (
            patch.object(app, "_wait_for_signal", new_callable=AsyncMock),
            pytest.raises(RuntimeError, match="health check failed"),
        ):
            await app.run()

        # Stop hooks should still run via finally
        assert "stop" in order


# ---------------------------------------------------------------------------
# 5. Logging setup with invalid/edge-case log level
# ---------------------------------------------------------------------------


class TestLoggingSetup:
    async def test_debug_mode_overrides_log_level(self) -> None:
        cfg = _cfg("svc", debug=True, logging=LoggingConfig(level="ERROR", format="json"))
        app = App(cfg)

        # Should not raise even though debug overrides log level
        await app.run_task(AsyncMock())

    async def test_production_logging_config(self) -> None:
        cfg = _cfg(
            "prod-svc",
            environment=Environment.PRODUCTION,
            logging=LoggingConfig(level="WARNING", format="json"),
        )
        app = App(cfg)
        await app.run_task(AsyncMock())


# ---------------------------------------------------------------------------
# 6. Multiple on_configure hooks with dependency order
# ---------------------------------------------------------------------------


class TestMultipleConfigureHooks:
    async def test_configure_hooks_execute_in_registration_order(self) -> None:
        order: list[int] = []
        lc = Lifecycle()
        for i in range(5):
            val = i

            async def hook(v: int = val) -> None:
                order.append(v)

            lc.on_configure(hook)

        await lc.run_configure_hooks()
        assert order == [0, 1, 2, 3, 4]

    async def test_configure_hook_can_depend_on_previous(self) -> None:
        """Second configure hook can use state set by the first."""
        state: dict[str, str] = {}
        app = App(_cfg("test"))

        async def set_db() -> None:
            state["db"] = "postgres://localhost"

        async def set_cache() -> None:
            assert "db" in state, "cache hook depends on db hook"
            state["cache"] = "redis://localhost"

        app.on_configure(set_db)
        app.on_configure(set_cache)

        await app.run_task(AsyncMock())
        assert state == {"db": "postgres://localhost", "cache": "redis://localhost"}


# ---------------------------------------------------------------------------
# 7. Config protocol methods called in wrong order
# ---------------------------------------------------------------------------


class TestConfigProtocol:
    def test_default_app_config_satisfies_protocol(self) -> None:
        cfg = _cfg("test")
        assert isinstance(cfg, AppConfig)

    def test_apply_defaults_before_service_config(self) -> None:
        cfg = DefaultAppConfig()
        # Before apply_defaults, name is empty
        assert cfg.service.name == ""
        cfg.apply_defaults()
        assert cfg.service.name == "unknown"
        # service_config should reflect the updated value
        assert cfg.service_config.name == "unknown"

    def test_custom_config_satisfies_protocol(self) -> None:
        """Custom class implementing AppConfig protocol."""

        class CustomConfig:
            def apply_defaults(self) -> None:
                pass

            @property
            def service_config(self) -> ServiceConfig:
                return ServiceConfig(name="custom")

        cfg = CustomConfig()
        assert isinstance(cfg, AppConfig)
        assert cfg.service_config.name == "custom"


# ---------------------------------------------------------------------------
# 8. Component registry failing during startup (partial component stop)
# ---------------------------------------------------------------------------


class TestPartialComponentStartup:
    async def test_partial_start_failure_still_stops_started_components(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))

        app.with_component(_MockComponent("db", order=order))
        app.with_component(_MockComponent("cache", order=order, start_error=RuntimeError("cache fail")))
        app.with_component(_MockComponent("kafka", order=order))

        with pytest.raises(RuntimeError, match="cache fail"):
            await app.run_task(AsyncMock())

        assert "db:start" in order
        assert "cache:start" in order
        # kafka should NOT have started
        assert "kafka:start" not in order
        # db and cache should be stopped (via finally in _shutdown)
        assert "db:stop" in order

    async def test_component_start_order_is_registration_order(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        for name in ["alpha", "beta", "gamma"]:
            app.with_component(_MockComponent(name, order=order))

        await app.run_task(AsyncMock())
        starts = [e for e in order if e.endswith(":start")]
        assert starts == ["alpha:start", "beta:start", "gamma:start"]

    async def test_component_stop_order_is_reverse_registration(self) -> None:
        order: list[str] = []
        app = App(_cfg("test"))
        for name in ["alpha", "beta", "gamma"]:
            app.with_component(_MockComponent(name, order=order))

        await app.run_task(AsyncMock())
        stops = [e for e in order if e.endswith(":stop")]
        assert stops == ["gamma:stop", "beta:stop", "alpha:stop"]


# ---------------------------------------------------------------------------
# 9. Fluent API chaining verification (returns self)
# ---------------------------------------------------------------------------


class TestFluentAPI:
    def test_with_component_chaining(self) -> None:
        app = App(_cfg("svc"))
        result = (
            app.with_component(_MockComponent("a"))
            .with_component(_MockComponent("b"))
            .with_component(_MockComponent("c"))
        )
        assert result is app

    def test_hook_chaining(self) -> None:
        app = App(_cfg("svc"))
        sentinel = AsyncMock()
        result = app.on_configure(sentinel).on_start(sentinel).on_ready(sentinel).on_stop(sentinel)
        assert result is app

    def test_set_ready_check_chaining(self) -> None:
        app = App(_cfg("svc"))
        result = app.set_ready_check(AsyncMock())
        assert result is app

    def test_mixed_chaining(self) -> None:
        app = App(_cfg("svc"))
        result = (
            app.with_component(_MockComponent("db"))
            .on_configure(AsyncMock())
            .on_start(AsyncMock())
            .with_component(_MockComponent("cache"))
            .on_stop(AsyncMock())
            .set_ready_check(AsyncMock())
        )
        assert result is app


# ---------------------------------------------------------------------------
# 10. Empty app (no components, no hooks) run_task
# ---------------------------------------------------------------------------


class TestEmptyApp:
    async def test_empty_app_run_task(self) -> None:
        app = App(_cfg("empty"))

        async def task() -> None:
            pass

        # Should complete without error
        await app.run_task(task)

    async def test_empty_app_run(self) -> None:
        app = App(_cfg("empty"))

        with patch.object(app, "_wait_for_signal", new_callable=AsyncMock):
            await app.run()

    async def test_empty_lifecycle_hooks_are_noop(self) -> None:
        lc = Lifecycle()
        # All should complete without error
        await lc.run_configure_hooks()
        await lc.run_start_hooks()
        await lc.run_ready_hooks()
        await lc.run_stop_hooks()


# ---------------------------------------------------------------------------
# Additional edge-case tests
# ---------------------------------------------------------------------------


class TestLifecycleEdgeCases:
    async def test_hook_exception_type_preserved(self) -> None:
        """Specific exception types should propagate unchanged."""
        lc = Lifecycle()

        async def type_error_hook() -> None:
            raise TypeError("wrong type")

        lc.on_start(type_error_hook)
        with pytest.raises(TypeError, match="wrong type"):
            await lc.run_start_hooks()

    async def test_many_hooks_all_run(self) -> None:
        """Verify a large number of hooks all execute."""
        count = 0
        lc = Lifecycle()

        for _ in range(50):

            async def hook() -> None:
                nonlocal count
                count += 1

            lc.on_start(hook)

        await lc.run_start_hooks()
        assert count == 50

    async def test_stop_hooks_reverse_with_single_hook(self) -> None:
        order: list[str] = []
        lc = Lifecycle()
        lc.on_stop(_make_hook(order, "only"))
        await lc.run_stop_hooks()
        assert order == ["only"]


class TestAppProperties:
    def test_config_property_returns_config(self) -> None:
        cfg = _cfg("svc", version="3.0")
        app = App(cfg)
        assert app.config is cfg
        assert app.config.service_config.name == "svc"

    def test_lifecycle_property(self) -> None:
        app = App(_cfg("svc"))
        assert isinstance(app.lifecycle, Lifecycle)

    def test_registry_property(self) -> None:
        app = App(_cfg("svc"))
        assert isinstance(app.registry, Registry)

    def test_graceful_timeout_custom(self) -> None:
        app = App(_cfg("svc"), graceful_timeout=5.0)
        assert app._graceful_timeout == 5.0

    def test_graceful_timeout_default(self) -> None:
        app = App(_cfg("svc"))
        assert app._graceful_timeout == 30.0

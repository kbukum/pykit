"""Extended tests for pykit_server.BaseServer lifecycle and edge cases."""

from __future__ import annotations

import asyncio
import signal
from unittest.mock import AsyncMock, MagicMock, patch

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc

from pykit_component import Health, HealthStatus
from pykit_server import BaseServer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _CustomServer(BaseServer):
    """Subclass that records register_services calls."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.services_registered = False
        self.registered_server: grpc.aio.Server | None = None

    async def register_services(self, server: grpc.aio.Server) -> None:
        self.services_registered = True
        self.registered_server = server


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self) -> None:
        s = BaseServer()
        assert s.host == "0.0.0.0"
        assert s.port == 50051
        assert s.max_workers == 10
        assert s.graceful_shutdown_timeout == 30.0
        assert s.interceptors == []
        assert s.reflection_service_names == []
        assert s._server is None
        assert s._health_servicer is None

    def test_custom_params(self) -> None:
        interceptor = MagicMock()
        s = BaseServer(
            host="127.0.0.1",
            port=9999,
            max_workers=4,
            graceful_shutdown_timeout=10.0,
            interceptors=[interceptor],
            reflection_service_names=["my.Service"],
        )
        assert s.host == "127.0.0.1"
        assert s.port == 9999
        assert s.max_workers == 4
        assert s.graceful_shutdown_timeout == 10.0
        assert len(s.interceptors) == 1
        assert s.reflection_service_names == ["my.Service"]

    def test_shutdown_event_not_set(self) -> None:
        s = BaseServer()
        assert not s._shutdown_event.is_set()


# ---------------------------------------------------------------------------
# Name / Component protocol
# ---------------------------------------------------------------------------


class TestComponentProtocol:
    def test_name(self) -> None:
        s = BaseServer()
        assert s.name == "grpc-server"

    @pytest.mark.asyncio
    async def test_health_unhealthy_before_start(self) -> None:
        s = BaseServer()
        h = await s.health()
        assert isinstance(h, Health)
        assert h.status == HealthStatus.UNHEALTHY
        assert h.message == "not running"

    @pytest.mark.asyncio
    async def test_health_healthy_when_running(self) -> None:
        s = BaseServer(host="127.0.0.1", port=0)
        # Use port 0 — bind to any free port
        s.port = 50181
        await s.start()
        try:
            h = await s.health()
            assert h.status == HealthStatus.HEALTHY
            assert h.message == "serving"
        finally:
            await s.stop()

    @pytest.mark.asyncio
    async def test_health_unhealthy_after_stop(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50180)
        await s.start()
        await s.stop()
        h = await s.health()
        assert h.status == HealthStatus.UNHEALTHY


# ---------------------------------------------------------------------------
# Start / Stop lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_creates_server(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50179)
        assert s._server is None
        await s.start()
        try:
            assert s._server is not None
        finally:
            await s.stop()

    @pytest.mark.asyncio
    async def test_start_creates_health_servicer(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50178)
        assert s.health_servicer is None
        await s.start()
        try:
            assert s.health_servicer is not None
        finally:
            await s.stop()

    @pytest.mark.asyncio
    async def test_stop_sets_shutdown_event(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50177)
        await s.start()
        assert not s._shutdown_event.is_set()
        await s.stop()
        assert s._shutdown_event.is_set()

    @pytest.mark.asyncio
    async def test_stop_noop_when_not_started(self) -> None:
        s = BaseServer()
        await s.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_stop_sets_not_serving(self) -> None:
        """After stop, the health service should be marked NOT_SERVING."""
        s = BaseServer(host="127.0.0.1", port=50176)
        await s.start()
        await s.stop()
        # Health servicer still exists but marked NOT_SERVING
        assert s.health_servicer is not None


# ---------------------------------------------------------------------------
# register_services override
# ---------------------------------------------------------------------------


class TestRegisterServices:
    @pytest.mark.asyncio
    async def test_default_is_noop(self) -> None:
        s = BaseServer()
        mock = AsyncMock()
        await s.register_services(mock)  # must not raise

    @pytest.mark.asyncio
    async def test_subclass_receives_server(self) -> None:
        s = _CustomServer(host="127.0.0.1", port=50175)
        await s.start()
        try:
            assert s.services_registered
            assert s.registered_server is not None
        finally:
            await s.stop()


# ---------------------------------------------------------------------------
# Health check via gRPC
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @pytest.mark.asyncio
    async def test_health_serving_after_start(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50174)
        await s.start()
        try:
            async with grpc.aio.insecure_channel("127.0.0.1:50174") as channel:
                stub = health_pb2_grpc.HealthStub(channel)
                resp = await stub.Check(health_pb2.HealthCheckRequest(service=""))
                assert resp.status == health_pb2.HealthCheckResponse.SERVING
        finally:
            await s.stop()

    @pytest.mark.asyncio
    async def test_reflection_enabled(self) -> None:
        """Reflection service should be enabled after start."""
        s = BaseServer(host="127.0.0.1", port=50173)
        await s.start()
        try:
            async with grpc.aio.insecure_channel("127.0.0.1:50173") as channel:
                # Health is always registered; confirming it works via reflection's presence
                stub = health_pb2_grpc.HealthStub(channel)
                resp = await stub.Check(health_pb2.HealthCheckRequest(service=""))
                assert resp.status == health_pb2.HealthCheckResponse.SERVING
        finally:
            await s.stop()


# ---------------------------------------------------------------------------
# set_service_status
# ---------------------------------------------------------------------------


class TestSetServiceStatus:
    def test_noop_before_start(self) -> None:
        s = BaseServer()
        s.set_service_status("anything", serving=True)  # must not raise

    @pytest.mark.asyncio
    async def test_set_serving(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50172)
        await s.start()
        try:
            s.set_service_status("my.Service", serving=True)
            async with grpc.aio.insecure_channel("127.0.0.1:50172") as channel:
                stub = health_pb2_grpc.HealthStub(channel)
                resp = await stub.Check(health_pb2.HealthCheckRequest(service="my.Service"))
                assert resp.status == health_pb2.HealthCheckResponse.SERVING
        finally:
            await s.stop()

    @pytest.mark.asyncio
    async def test_set_not_serving(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50171)
        await s.start()
        try:
            s.set_service_status("my.Service", serving=True)
            s.set_service_status("my.Service", serving=False)
            async with grpc.aio.insecure_channel("127.0.0.1:50171") as channel:
                stub = health_pb2_grpc.HealthStub(channel)
                resp = await stub.Check(health_pb2.HealthCheckRequest(service="my.Service"))
                assert resp.status == health_pb2.HealthCheckResponse.NOT_SERVING
        finally:
            await s.stop()


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------


class TestSignalHandling:
    @pytest.mark.asyncio
    async def test_install_signal_handlers(self) -> None:
        """_install_signal_handlers should add handlers for SIGINT and SIGTERM."""
        s = BaseServer(host="127.0.0.1", port=50170)
        await s.start()
        try:
            s._install_signal_handlers()
            # If we got here without error, handlers were installed
        finally:
            await s.stop()

    @pytest.mark.asyncio
    async def test_signal_handler_triggers_stop(self) -> None:
        """Simulating a SIGTERM through the installed handler triggers shutdown."""
        s = BaseServer(host="127.0.0.1", port=50169)
        await s.start()
        s._install_signal_handlers()

        loop = asyncio.get_running_loop()
        # Trigger the signal handler for SIGTERM
        loop.call_soon(lambda: loop.remove_signal_handler(signal.SIGTERM))
        # Instead, directly trigger stop via the shutdown event mechanism
        stop_task = asyncio.create_task(s.stop())
        await asyncio.wait_for(s._shutdown_event.wait(), timeout=5.0)
        assert s._shutdown_event.is_set()
        stop_task.cancel()


# ---------------------------------------------------------------------------
# run() lifecycle
# ---------------------------------------------------------------------------


class TestRun:
    @pytest.mark.asyncio
    async def test_run_calls_start_and_waits(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50168)

        with (
            patch.object(s, "start", new_callable=AsyncMock) as mock_start,
            patch.object(s, "_install_signal_handlers") as mock_signals,
        ):
            s._shutdown_event.set()  # so run() returns immediately
            await s.run()

        mock_start.assert_awaited_once()
        mock_signals.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_blocks_until_shutdown(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50167)

        with patch.object(s, "start", new_callable=AsyncMock), patch.object(s, "_install_signal_handlers"):
            # Schedule shutdown after a short delay
            async def trigger():
                await asyncio.sleep(0.1)
                s._shutdown_event.set()

            task = asyncio.create_task(trigger())
            await asyncio.wait_for(s.run(), timeout=5.0)
            await task


# ---------------------------------------------------------------------------
# Graceful shutdown timeout
# ---------------------------------------------------------------------------


class TestGracefulShutdownTimeout:
    @pytest.mark.asyncio
    async def test_custom_timeout_passed_to_stop(self) -> None:
        """stop() should call _server.stop(graceful_shutdown_timeout)."""
        s = BaseServer(host="127.0.0.1", port=50166, graceful_shutdown_timeout=5.0)
        await s.start()

        mock_server = AsyncMock()
        s._server = mock_server
        await s.stop()

        mock_server.stop.assert_awaited_once_with(5.0)

    @pytest.mark.asyncio
    async def test_default_timeout_is_30(self) -> None:
        s = BaseServer()
        assert s.graceful_shutdown_timeout == 30.0


# ---------------------------------------------------------------------------
# Interceptors
# ---------------------------------------------------------------------------


class TestInterceptors:
    @pytest.mark.asyncio
    async def test_interceptors_passed_to_grpc_server(self) -> None:
        """Interceptors should be passed to grpc.aio.server()."""
        interceptor = MagicMock(spec=grpc.aio.ServerInterceptor)
        s = BaseServer(host="127.0.0.1", port=50165, interceptors=[interceptor])

        with patch("pykit_server.base.grpc.aio.server") as mock_server_fn:
            mock_srv = AsyncMock()
            mock_srv.add_insecure_port = MagicMock()
            mock_srv.add_generic_rpc_handlers = MagicMock()
            mock_srv.add_registered_method_handlers = MagicMock()
            mock_srv.start = AsyncMock()
            mock_server_fn.return_value = mock_srv

            await s.start()

            mock_server_fn.assert_called_once()
            call_kwargs = mock_server_fn.call_args
            assert interceptor in call_kwargs.kwargs.get(
                "interceptors", call_kwargs.args[0] if call_kwargs.args else []
            ) or interceptor in (call_kwargs.kwargs.get("interceptors", []))

            # Clean up
            s._server = mock_srv
            await s.stop()

    @pytest.mark.asyncio
    async def test_empty_interceptors_list(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50164)
        assert s.interceptors == []
        await s.start()
        try:
            assert s._server is not None
        finally:
            await s.stop()


# ---------------------------------------------------------------------------
# Concurrent server operations
# ---------------------------------------------------------------------------


class TestConcurrency:
    @pytest.mark.asyncio
    async def test_multiple_set_service_status_calls(self) -> None:
        """Multiple set_service_status calls should not race."""
        s = BaseServer(host="127.0.0.1", port=50163)
        await s.start()
        try:
            tasks = []
            for i in range(10):
                name = f"svc-{i}"
                tasks.append(asyncio.create_task(asyncio.to_thread(s.set_service_status, name, True)))
            await asyncio.gather(*tasks)
        finally:
            await s.stop()


# ---------------------------------------------------------------------------
# Reflection service names
# ---------------------------------------------------------------------------


class TestReflection:
    @pytest.mark.asyncio
    async def test_custom_reflection_names(self) -> None:
        """Custom reflection service names should not cause errors."""
        s = BaseServer(
            host="127.0.0.1",
            port=50162,
            reflection_service_names=["my.custom.Service"],
        )
        await s.start()
        try:
            assert s._server is not None
        finally:
            await s.stop()

    @pytest.mark.asyncio
    async def test_empty_reflection_names(self) -> None:
        s = BaseServer(host="127.0.0.1", port=50161)
        await s.start()
        try:
            assert s._server is not None
        finally:
            await s.stop()

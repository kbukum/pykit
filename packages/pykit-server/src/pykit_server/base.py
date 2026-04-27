"""BaseServer — gRPC server bootstrap with health service and graceful shutdown.

Supports gRPC reflection for service discovery out of the box. Use ``grpcurl``
to list and call services on a running server::

    # List all services
    grpcurl -plaintext localhost:50051 list

    # Describe a service
    grpcurl -plaintext localhost:50051 describe my.package.MyService

    # Call an RPC
    grpcurl -plaintext -d '{"field": "value"}' localhost:50051 my.package.MyService/MyMethod

Reflection is enabled by default. Disable via ``reflection_enabled=False``::

    server = MyServer(reflection_enabled=False)
"""

from __future__ import annotations

import asyncio
import signal

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

import pykit_logging as log
from pykit_component import Health, HealthStatus


class BaseServer:
    """Generic gRPC server with health checking, reflection, and graceful shutdown.

    Subclass and override ``register_services`` to add your gRPC service
    implementations. Reflection is enabled by default so tools like ``grpcurl``
    can discover services without a proto file.

    Parameters
    ----------
    host:
        Bind address (default ``"0.0.0.0"``).
    port:
        TCP port (default ``50051``).
    max_workers:
        Maximum concurrent RPC handlers.
    graceful_shutdown_timeout:
        Seconds to wait for in-flight RPCs during shutdown.
    interceptors:
        Optional list of gRPC server interceptors.
    reflection_service_names:
        Fully-qualified gRPC service names to advertise via reflection.
        The health and reflection services are always included automatically.
    reflection_enabled:
        Whether to enable gRPC server reflection (default ``True``).
    """

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",
        port: int = 50051,
        max_workers: int = 10,
        graceful_shutdown_timeout: float = 30.0,
        interceptors: list[grpc.aio.ServerInterceptor] | None = None,
        reflection_service_names: list[str] | None = None,
        reflection_enabled: bool = True,
    ) -> None:
        self.host = host
        self.port = port
        self.max_workers = max_workers
        self.graceful_shutdown_timeout = graceful_shutdown_timeout
        self.interceptors = interceptors or []
        self.reflection_service_names = reflection_service_names or []
        self.reflection_enabled = reflection_enabled
        self._server: grpc.aio.Server | None = None
        self._health_servicer: health.HealthServicer | None = None
        self._shutdown_event = asyncio.Event()
        self._stop_task: asyncio.Task[None] | None = None
        self.logger = log.get_logger(__name__)

    @property
    def name(self) -> str:
        """Component name for registry identification."""
        return "grpc-server"

    async def start(self) -> None:
        """Create, configure, and start the gRPC server."""
        self._server = grpc.aio.server(interceptors=self.interceptors)

        # Health service
        self._health_servicer = health.HealthServicer()
        health_pb2_grpc.add_HealthServicer_to_server(self._health_servicer, self._server)

        # Let subclasses register their services
        await self.register_services(self._server)

        # Set health status for registered services
        self._health_servicer.set(
            "",
            health_pb2.HealthCheckResponse.SERVING,
        )

        if self.reflection_enabled:
            service_names = [
                *self.reflection_service_names,
                health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
                reflection.SERVICE_NAME,
            ]
            reflection.enable_server_reflection(service_names, self._server)
            self.logger.info(
                "gRPC reflection enabled",
                services=service_names,
            )

        bind_address = f"{self.host}:{self.port}"
        self._server.add_insecure_port(bind_address)
        await self._server.start()
        self.logger.info("gRPC server started", address=bind_address)

    async def register_services(self, server: grpc.aio.Server) -> None:
        """Override to register gRPC service implementations on the server."""

    async def stop(self) -> None:
        """Gracefully stop the server."""
        if self._server is None:
            return

        self.logger.info("Shutting down gRPC server...")

        if self._health_servicer is not None:
            self._health_servicer.set(
                "",
                health_pb2.HealthCheckResponse.NOT_SERVING,
            )

        await self._server.stop(self.graceful_shutdown_timeout)
        self._shutdown_event.set()
        self.logger.info("gRPC server stopped")

    async def run(self) -> None:
        """Start the server and wait for shutdown signal."""
        await self.start()
        self._install_signal_handlers()
        await self._shutdown_event.wait()

    def _install_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown."""
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._schedule_stop)

    def _schedule_stop(self) -> None:
        """Schedule stop() as a task, storing the reference to prevent GC."""
        if self._stop_task is None or self._stop_task.done():
            self._stop_task = asyncio.create_task(self.stop())

    @property
    def health_servicer(self) -> health.HealthServicer | None:
        return self._health_servicer

    def set_service_status(self, service_name: str, serving: bool = True) -> None:
        """Update the health status for a named service."""
        if self._health_servicer is None:
            return
        status = (
            health_pb2.HealthCheckResponse.SERVING if serving else health_pb2.HealthCheckResponse.NOT_SERVING
        )
        self._health_servicer.set(service_name, status)

    async def health(self) -> Health:
        """Return component health based on server state."""
        if self._server is not None and not self._shutdown_event.is_set():
            return Health(name=self.name, status=HealthStatus.HEALTHY, message="serving")
        return Health(name=self.name, status=HealthStatus.UNHEALTHY, message="not running")

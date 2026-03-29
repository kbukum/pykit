"""BaseServer — gRPC server bootstrap with health service and graceful shutdown."""

from __future__ import annotations

import asyncio
import signal

import grpc
from grpc_health.v1 import health, health_pb2, health_pb2_grpc
from grpc_reflection.v1alpha import reflection

import pykit_logging as log


class BaseServer:
    """Generic gRPC server with health checking, reflection, and graceful shutdown.

    Subclass and override `register_services` to add your gRPC service implementations.
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
    ) -> None:
        self.host = host
        self.port = port
        self.max_workers = max_workers
        self.graceful_shutdown_timeout = graceful_shutdown_timeout
        self.interceptors = interceptors or []
        self.reflection_service_names = reflection_service_names or []
        self._server: grpc.aio.Server | None = None
        self._health_servicer: health.HealthServicer | None = None
        self._shutdown_event = asyncio.Event()
        self.logger = log.get_logger(__name__)

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
        service_names = [
            *self.reflection_service_names,
            health_pb2.DESCRIPTOR.services_by_name["Health"].full_name,
            reflection.SERVICE_NAME,
        ]
        reflection.enable_server_reflection(service_names, self._server)

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
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

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

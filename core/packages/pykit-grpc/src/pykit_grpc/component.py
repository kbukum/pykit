"""Lifecycle component wrapping a GrpcChannel."""

from __future__ import annotations

from pykit_component import Health, HealthStatus
from pykit_grpc.channel import GrpcChannel
from pykit_grpc.config import GrpcConfig


class GrpcComponent:
    """Implements the :class:`pykit_component.Component` protocol for a gRPC channel.

    Manages channel creation on ``start``, teardown on ``stop``, and
    connectivity-based health reporting.
    """

    def __init__(self, config: GrpcConfig, *, component_name: str = "grpc") -> None:
        self._config = config
        self._name = component_name
        self._grpc_channel: GrpcChannel | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def grpc_channel(self) -> GrpcChannel | None:
        """Return the managed :class:`GrpcChannel`, or *None* before start."""
        return self._grpc_channel

    async def start(self) -> None:
        """Create the underlying channel."""
        self._grpc_channel = GrpcChannel(self._config)

    async def stop(self) -> None:
        """Close the underlying channel."""
        if self._grpc_channel is not None:
            await self._grpc_channel.close()
            self._grpc_channel = None

    async def health(self) -> Health:
        """Check channel connectivity and report health."""
        if self._grpc_channel is None:
            return Health(name=self._name, status=HealthStatus.UNHEALTHY, message="channel not started")

        try:
            connected = await self._grpc_channel.ping()
        except Exception as exc:
            return Health(name=self._name, status=HealthStatus.UNHEALTHY, message=str(exc))

        if connected:
            return Health(name=self._name, status=HealthStatus.HEALTHY)
        return Health(name=self._name, status=HealthStatus.DEGRADED, message="channel not ready")

"""Discovery-aware async gRPC channel with health checks and reconnection."""

from __future__ import annotations

import asyncio

import grpc
from grpc import aio

from pykit_discovery.protocols import Discovery
from pykit_discovery.types import ServiceInstance
from pykit_grpc.config import GrpcConfig


class DiscoveryChannel:
    """An async gRPC channel that resolves services via discovery and reconnects on changes.

    This channel wraps a :class:`grpc.aio.Channel` and adds:
    - Service discovery integration (resolves service names to concrete endpoints)
    - Automatic health checks via ping()
    - Optional channel refresh when targets change
    - Drop-in replacement for :class:`GrpcChannel`

    The channel caches the resolved target and reuses it until explicitly refreshed
    or a connectivity issue is detected.
    """

    def __init__(
        self,
        discovery: Discovery,
        service_name: str,
        config: GrpcConfig | None = None,
    ) -> None:
        """Initialize a discovery-aware gRPC channel.

        Args:
            discovery: The discovery client to use for resolving services.
            service_name: The name of the service to discover.
            config: Optional gRPC config for message sizes, timeouts, and TLS.
                    If None, uses GrpcConfig defaults.
        """
        self._discovery = discovery
        self._service_name = service_name
        self._config = config or GrpcConfig()
        self._channel: aio.Channel | None = None
        self._current_instance: ServiceInstance | None = None
        self._resolved_target: str | None = None
        self._lock = asyncio.Lock()

    async def resolve(self) -> str:
        """Discover a service instance and return its target address.

        This method queries the discovery client for healthy instances of the service,
        selects one (using the discovery client's strategy), and returns its address.

        Returns:
            The resolved target address (host:port).

        Raises:
            RuntimeError: If no healthy instances are available.
        """
        instances = await self._discovery.discover(self._service_name)
        if not instances:
            raise RuntimeError(f"No healthy instances for service {self._service_name}")

        # Use the first healthy instance (discovery may already apply load balancing)
        instance = next(
            (inst for inst in instances if inst.healthy),
            instances[0] if instances else None,
        )
        if not instance:
            raise RuntimeError(f"No healthy instances for service {self._service_name}")

        self._current_instance = instance
        target = instance.address
        self._resolved_target = target
        return target

    @property
    def channel(self) -> aio.Channel:
        """Return the underlying :class:`grpc.aio.Channel`.

        On first access, this method creates and caches the channel to the
        discovered service target. Subsequent accesses return the cached channel.
        """
        if self._channel is None:
            raise RuntimeError(
                "Channel not yet initialized. Call resolve() or refresh() first."
            )
        return self._channel

    async def refresh(self) -> None:
        """Discover and reconnect to service if the target has changed.

        This method is useful when you want to force a fresh discovery and
        reconnection. It will close the existing channel if the target changed
        and create a new one to the new endpoint.

        If the target has not changed, this method is a no-op.
        """
        async with self._lock:
            try:
                # Save the old target before resolving
                old_target = self._resolved_target

                # Resolve the new target
                new_target = await self.resolve()

                # If target changed, close old channel and create new one
                if old_target != new_target or self._channel is None:
                    if self._channel is not None:
                        await self._channel.close()

                    # Create new channel to the resolved target
                    self._channel = self._create_channel(new_target)
            except Exception as e:
                raise RuntimeError(f"Failed to refresh channel: {e}") from e

    async def close(self) -> None:
        """Close the channel gracefully."""
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._resolved_target = None

    async def ping(self) -> bool:
        """Return True if the channel is in a connected/ready state.

        This performs a lightweight health check by checking the channel's
        connectivity state and optionally triggering a connection attempt.
        """
        if self._channel is None:
            return False

        try:
            state = self._channel.get_state(try_to_connect=True)
            return state == grpc.ChannelConnectivity.READY
        except Exception:
            return False

    def _create_channel(self, target: str) -> aio.Channel:
        """Create an aio.Channel to the given target with configured options."""
        options: list[tuple[str, int]] = [
            ("grpc.max_send_message_length", self._config.max_message_size),
            ("grpc.max_receive_message_length", self._config.max_message_size),
            ("grpc.keepalive_time_ms", int(self._config.keepalive_time * 1000)),
            ("grpc.keepalive_timeout_ms", int(self._config.keepalive_timeout * 1000)),
        ]

        if self._config.insecure:
            return aio.insecure_channel(target, options=options)
        else:
            credentials = grpc.ssl_channel_credentials()
            return aio.secure_channel(target, credentials, options=options)

    async def __aenter__(self) -> DiscoveryChannel:
        """Async context manager entry: initialize and return self."""
        await self.refresh()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit: close the channel."""
        await self.close()

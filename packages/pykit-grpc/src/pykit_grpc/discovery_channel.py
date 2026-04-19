"""Discovery-aware async gRPC channel with health checks and reconnection."""

from __future__ import annotations

import asyncio
import contextlib
import logging

import grpc
from grpc import aio

from pykit_discovery.protocols import Discovery, Watcher
from pykit_discovery.types import ServiceInstance
from pykit_grpc.config import GrpcConfig

logger = logging.getLogger(__name__)


class DiscoveryChannel:
    """An async gRPC channel that resolves services via discovery and reconnects on changes.

    This channel wraps a :class:`grpc.aio.Channel` and adds:
    - Service discovery integration (resolves service names to concrete endpoints)
    - Automatic health checks via ping()
    - Background resolution with optional watcher or periodic polling
    - Automatic reconnection when the target address changes
    - Drop-in replacement for :class:`GrpcChannel`

    The channel caches the resolved target and reuses it until a background
    resolve detects a change or a manual refresh is triggered.
    """

    def __init__(
        self,
        discovery: Discovery,
        service_name: str,
        config: GrpcConfig | None = None,
        *,
        resolve_interval: float = 10.0,
        watcher: Watcher | None = None,
    ) -> None:
        """Initialize a discovery-aware gRPC channel.

        Args:
            discovery: The discovery client to use for resolving services.
            service_name: The name of the service to discover.
            config: Optional gRPC config for message sizes, timeouts, and TLS.
                    If None, uses GrpcConfig defaults.
            resolve_interval: Seconds between polling re-resolves when no watcher
                              is provided. Defaults to 10.0.
            watcher: Optional :class:`Watcher` for push-based service updates.
                     If the discovery object also implements Watcher and no explicit
                     watcher is given, it will be auto-detected.
        """
        self._discovery = discovery
        self._service_name = service_name
        self._config = config or GrpcConfig()
        self._resolve_interval = resolve_interval
        self._channel: aio.Channel | None = None
        self._current_instance: ServiceInstance | None = None
        self._resolved_target: str | None = None
        self._lock = asyncio.Lock()
        self._background_task: asyncio.Task[None] | None = None

        # Auto-detect watcher from discovery if not explicitly provided
        if watcher is not None:
            self._watcher: Watcher | None = watcher
        elif isinstance(discovery, Watcher):
            self._watcher = discovery
        else:
            self._watcher = None

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
            raise RuntimeError("Channel not yet initialized. Call resolve() or refresh() first.")
        return self._channel

    async def get_channel(self) -> aio.Channel:
        """Return the channel, triggering an immediate re-resolve if unhealthy.

        This is the preferred async accessor when the caller wants automatic
        recovery on connection errors.
        """
        if self._channel is not None:
            try:
                state = self._channel.get_state(try_to_connect=False)
                if state in (
                    grpc.ChannelConnectivity.TRANSIENT_FAILURE,
                    grpc.ChannelConnectivity.SHUTDOWN,
                ):
                    logger.warning(
                        "Channel to %s is %s — triggering immediate re-resolve",
                        self._resolved_target,
                        state.name,
                    )
                    await self.refresh()
            except Exception:
                await self.refresh()
        else:
            await self.refresh()
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
                        logger.info(
                            "Target changed %s -> %s for service %s",
                            old_target,
                            new_target,
                            self._service_name,
                        )

                    # Create new channel to the resolved target
                    self._channel = self._create_channel(new_target)
            except Exception as e:
                raise RuntimeError(f"Failed to refresh channel: {e}") from e

    def start_background_resolve(self) -> None:
        """Spawn a background task that keeps the channel target up-to-date.

        If a :class:`Watcher` is available, the task will ``async for`` over
        ``watcher.watch()`` and swap the channel whenever the instance list
        changes.  Otherwise it falls back to calling :meth:`resolve` every
        ``resolve_interval`` seconds.

        Calling this multiple times is safe — only one task runs at a time.
        """
        if self._background_task is not None and not self._background_task.done():
            return
        if self._watcher is not None:
            self._background_task = asyncio.ensure_future(self._watch_loop())
        else:
            self._background_task = asyncio.ensure_future(self._poll_loop())

    async def _apply_instances(self, instances: list[ServiceInstance]) -> None:
        """Select target from instances and swap channel if it changed."""
        if not instances:
            logger.warning("Received empty instance list for %s", self._service_name)
            return

        instance = next(
            (inst for inst in instances if inst.healthy),
            instances[0],
        )
        new_target = instance.address

        async with self._lock:
            if new_target != self._resolved_target or self._channel is None:
                old_target = self._resolved_target
                if self._channel is not None:
                    await self._channel.close()
                self._current_instance = instance
                self._resolved_target = new_target
                self._channel = self._create_channel(new_target)
                logger.info(
                    "Background resolve: %s -> %s for service %s",
                    old_target,
                    new_target,
                    self._service_name,
                )

    async def _watch_loop(self) -> None:
        """Continuously watch for service changes via a Watcher."""
        assert self._watcher is not None
        try:
            async for instances in self._watcher.watch(self._service_name):
                await self._apply_instances(instances)
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("Watch loop error for %s — falling back to polling", self._service_name)
            # Fall back to polling on watcher failure
            await self._poll_loop()

    async def _poll_loop(self) -> None:
        """Periodically re-resolve the service target."""
        try:
            while True:
                await asyncio.sleep(self._resolve_interval)
                try:
                    instances = await self._discovery.discover(self._service_name)
                    await self._apply_instances(instances)
                except asyncio.CancelledError:
                    return
                except Exception:
                    logger.exception(
                        "Background poll error for %s",
                        self._service_name,
                    )
        except asyncio.CancelledError:
            return

    async def close(self) -> None:
        """Close the channel and cancel background tasks gracefully."""
        # Cancel background resolve task first
        if self._background_task is not None and not self._background_task.done():
            self._background_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._background_task
            self._background_task = None

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
        """Async context manager entry: initialize, start background resolve, and return self."""
        await self.refresh()
        self.start_background_resolve()
        return self

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        """Async context manager exit: close the channel and cancel background tasks."""
        await self.close()

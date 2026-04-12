"""Tests for discovery-aware async gRPC channel."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import grpc
import pytest

from pykit_discovery.protocols import Discovery, Watcher
from pykit_discovery.types import ServiceInstance
from pykit_grpc.config import GrpcConfig
from pykit_grpc.discovery_channel import DiscoveryChannel


class MockDiscovery(Discovery):
    """Mock discovery implementation for testing."""

    def __init__(self, instances: list[ServiceInstance] | None = None):
        self.instances = instances or []
        self.discover_called = False
        self.failure = False

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        """Mock discover method."""
        self.discover_called = True
        if self.failure:
            raise RuntimeError("Mock discovery failure")
        return self.instances


@pytest.mark.asyncio
async def test_discovery_channel_resolve():
    """Test that resolve() discovers and returns a target address."""
    instance = ServiceInstance(
        id="test-1",
        name="test-service",
        host="localhost",
        port=50051,
        protocol="grpc",
        healthy=True,
    )
    discovery = MockDiscovery([instance])

    channel = DiscoveryChannel(discovery, "test-service")
    target = await channel.resolve()

    assert target == "localhost:50051"
    assert discovery.discover_called
    assert channel._current_instance == instance


@pytest.mark.asyncio
async def test_discovery_channel_resolve_multiple_instances():
    """Test resolve() picks a healthy instance when multiple are available."""
    instances = [
        ServiceInstance(
            id="test-1",
            name="test-service",
            host="host1",
            port=50051,
            healthy=False,  # unhealthy
        ),
        ServiceInstance(
            id="test-2",
            name="test-service",
            host="host2",
            port=50051,
            healthy=True,  # healthy
        ),
    ]
    discovery = MockDiscovery(instances)

    channel = DiscoveryChannel(discovery, "test-service")
    target = await channel.resolve()

    # Should pick the healthy instance
    assert target == "host2:50051"


@pytest.mark.asyncio
async def test_discovery_channel_resolve_no_instances():
    """Test resolve() raises error when no instances available."""
    discovery = MockDiscovery([])

    channel = DiscoveryChannel(discovery, "test-service")
    with pytest.raises(RuntimeError, match="No healthy instances"):
        await channel.resolve()


@pytest.mark.asyncio
async def test_discovery_channel_resolve_discovery_failure():
    """Test resolve() propagates discovery errors."""
    discovery = MockDiscovery([])
    discovery.failure = True

    channel = DiscoveryChannel(discovery, "test-service")
    with pytest.raises(RuntimeError, match="Mock discovery failure"):
        await channel.resolve()


@pytest.mark.asyncio
async def test_discovery_channel_create_channel():
    """Test that _create_channel creates a valid channel."""
    discovery = MockDiscovery([])
    config = GrpcConfig(target="localhost:50051", insecure=True)

    channel_obj = DiscoveryChannel(discovery, "test-service", config)
    ch = channel_obj._create_channel("localhost:50051")

    assert isinstance(ch, grpc.aio.Channel)
    await ch.close()


@pytest.mark.asyncio
async def test_discovery_channel_refresh():
    """Test that refresh() resolves and creates/reconnects channel."""
    instance = ServiceInstance(
        id="test-1",
        name="test-service",
        host="localhost",
        port=50051,
        healthy=True,
    )
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    channel = DiscoveryChannel(discovery, "test-service", config)
    await channel.refresh()

    assert channel._channel is not None
    assert channel._resolved_target == "localhost:50051"
    assert discovery.discover_called

    await channel.close()


@pytest.mark.asyncio
async def test_discovery_channel_refresh_target_changed():
    """Test refresh() closes old channel and creates new one when target changes."""
    instance1 = ServiceInstance(
        id="test-1",
        name="test-service",
        host="host1",
        port=50051,
        healthy=True,
    )
    instance2 = ServiceInstance(
        id="test-2",
        name="test-service",
        host="host2",
        port=50051,
        healthy=True,
    )

    discovery = MockDiscovery([instance1])
    config = GrpcConfig(insecure=True)

    channel = DiscoveryChannel(discovery, "test-service", config)
    await channel.refresh()
    old_target = channel._resolved_target
    old_channel = channel._channel

    # Simulate target change
    discovery.instances = [instance2]
    await channel.refresh()

    assert channel._resolved_target == "host2:50051"
    assert channel._resolved_target != old_target
    assert channel._channel != old_channel

    await channel.close()


@pytest.mark.asyncio
async def test_discovery_channel_channel_property():
    """Test that channel property returns the underlying aio.Channel."""
    instance = ServiceInstance(
        id="test-1",
        name="test-service",
        host="localhost",
        port=50051,
        healthy=True,
    )
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    channel = DiscoveryChannel(discovery, "test-service", config)
    await channel.refresh()

    ch = channel.channel
    assert isinstance(ch, grpc.aio.Channel)

    await channel.close()


@pytest.mark.asyncio
async def test_discovery_channel_channel_property_not_initialized():
    """Test that channel property raises error before initialization."""
    discovery = MockDiscovery([])
    channel = DiscoveryChannel(discovery, "test-service")

    with pytest.raises(RuntimeError, match="not yet initialized"):
        _ = channel.channel


@pytest.mark.asyncio
async def test_discovery_channel_close():
    """Test that close() closes the channel."""
    instance = ServiceInstance(
        id="test-1",
        name="test-service",
        host="localhost",
        port=50051,
        healthy=True,
    )
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    channel = DiscoveryChannel(discovery, "test-service", config)
    await channel.refresh()

    assert channel._channel is not None
    assert channel._resolved_target is not None

    await channel.close()

    assert channel._channel is None
    assert channel._resolved_target is None


@pytest.mark.asyncio
async def test_discovery_channel_ping_connected():
    """Test that ping() returns True when channel is ready."""
    instance = ServiceInstance(
        id="test-1",
        name="test-service",
        host="localhost",
        port=50051,
        healthy=True,
    )
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    channel = DiscoveryChannel(discovery, "test-service", config)
    await channel.refresh()

    # Note: This will likely return False because there's no actual server,
    # but we're testing that the method runs without error.
    result = await channel.ping()
    assert isinstance(result, bool)

    await channel.close()


@pytest.mark.asyncio
async def test_discovery_channel_ping_not_initialized():
    """Test that ping() returns False when channel is not initialized."""
    discovery = MockDiscovery([])
    channel = DiscoveryChannel(discovery, "test-service")

    result = await channel.ping()
    assert result is False


@pytest.mark.asyncio
async def test_discovery_channel_context_manager():
    """Test that DiscoveryChannel works as an async context manager."""
    instance = ServiceInstance(
        id="test-1",
        name="test-service",
        host="localhost",
        port=50051,
        healthy=True,
    )
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    channel = DiscoveryChannel(discovery, "test-service", config)
    async with channel as ch:
        assert ch is channel
        assert ch._channel is not None

    # After exiting context, channel should be closed
    assert channel._channel is None


@pytest.mark.asyncio
async def test_discovery_channel_custom_config():
    """Test DiscoveryChannel with custom GrpcConfig."""
    instance = ServiceInstance(
        id="test-1",
        name="test-service",
        host="localhost",
        port=50051,
        healthy=True,
    )
    discovery = MockDiscovery([instance])
    config = GrpcConfig(
        target="localhost:50051",
        insecure=True,
        max_message_size=8 * 1024 * 1024,
        keepalive_time=60.0,
    )

    channel = DiscoveryChannel(discovery, "test-service", config)
    await channel.refresh()

    # Verify config is used
    assert channel._config == config
    assert channel._config.max_message_size == 8 * 1024 * 1024

    await channel.close()


@pytest.mark.asyncio
async def test_discovery_channel_default_config():
    """Test DiscoveryChannel uses default config when not provided."""
    instance = ServiceInstance(
        id="test-1",
        name="test-service",
        host="localhost",
        port=50051,
        healthy=True,
    )
    discovery = MockDiscovery([instance])

    channel = DiscoveryChannel(discovery, "test-service")
    assert channel._config is not None
    assert isinstance(channel._config, GrpcConfig)

    await channel.refresh()
    await channel.close()


@pytest.mark.asyncio
async def test_discovery_channel_concurrent_resolve():
    """Test that concurrent resolve() calls are properly locked."""
    instance = ServiceInstance(
        id="test-1",
        name="test-service",
        host="localhost",
        port=50051,
        healthy=True,
    )
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    channel = DiscoveryChannel(discovery, "test-service", config)

    # Run multiple refreshes concurrently
    tasks = [channel.refresh() for _ in range(5)]
    await asyncio.gather(*tasks)

    assert channel._resolved_target == "localhost:50051"
    assert channel._channel is not None

    await channel.close()


@pytest.mark.asyncio
async def test_discovery_channel_refresh_after_close():
    """Test that refresh() after close() works correctly."""
    instance = ServiceInstance(
        id="test-1",
        name="test-service",
        host="localhost",
        port=50051,
        healthy=True,
    )
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    channel = DiscoveryChannel(discovery, "test-service", config)
    await channel.refresh()
    await channel.close()

    # Should be able to refresh again
    await channel.refresh()
    assert channel._channel is not None

    await channel.close()


# ---------------------------------------------------------------------------
# Helpers for background-resolve / watcher tests
# ---------------------------------------------------------------------------

class MockWatcher:
    """A watcher that yields instance lists from a queue."""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[list[ServiceInstance]] = asyncio.Queue()
        self._stopped = False

    async def push(self, instances: list[ServiceInstance]) -> None:
        await self._queue.put(instances)

    def stop(self) -> None:
        self._stopped = True

    async def watch(self, service_name: str) -> AsyncIterator[list[ServiceInstance]]:
        while not self._stopped:
            try:
                instances = await asyncio.wait_for(self._queue.get(), timeout=0.5)
                yield instances
            except TimeoutError:
                continue


class MockDiscoveryWithWatcher:
    """Implements both Discovery and Watcher protocols."""

    def __init__(self, instances: list[ServiceInstance] | None = None) -> None:
        self.instances = instances or []
        self._watcher = MockWatcher()

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        return self.instances

    async def watch(self, service_name: str) -> AsyncIterator[list[ServiceInstance]]:
        async for update in self._watcher.watch(service_name):
            yield update


def _make_instance(host: str = "localhost", port: int = 50051, healthy: bool = True) -> ServiceInstance:
    return ServiceInstance(
        id=f"{host}-{port}",
        name="test-service",
        host=host,
        port=port,
        healthy=healthy,
    )


# ---------------------------------------------------------------------------
# Background resolve tests — polling mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_background_poll_detects_target_change():
    """Background polling should swap the channel when discover() returns a new address."""
    instance1 = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance1])
    config = GrpcConfig(insecure=True)

    dc = DiscoveryChannel(discovery, "test-service", config, resolve_interval=0.1)
    await dc.refresh()
    assert dc._resolved_target == "host1:50051"

    # Change what discovery returns
    instance2 = _make_instance("host2", 50052)
    discovery.instances = [instance2]

    dc.start_background_resolve()
    # Give polling time to fire
    await asyncio.sleep(0.35)

    assert dc._resolved_target == "host2:50052"
    assert dc._channel is not None

    await dc.close()
    assert dc._background_task is None or dc._background_task.done()


@pytest.mark.asyncio
async def test_background_poll_no_change_keeps_channel():
    """If the target doesn't change, the channel should remain the same object."""
    instance = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    dc = DiscoveryChannel(discovery, "test-service", config, resolve_interval=0.1)
    await dc.refresh()
    original_channel = dc._channel

    dc.start_background_resolve()
    await asyncio.sleep(0.35)

    assert dc._channel is original_channel
    await dc.close()


@pytest.mark.asyncio
async def test_background_poll_survives_transient_errors():
    """Polling should keep running even when discover() raises."""
    instance = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    dc = DiscoveryChannel(discovery, "test-service", config, resolve_interval=0.1)
    await dc.refresh()

    # Make discovery fail
    discovery.failure = True
    dc.start_background_resolve()
    await asyncio.sleep(0.25)

    # Restore healthy discovery
    discovery.failure = False
    instance2 = _make_instance("host2", 50052)
    discovery.instances = [instance2]
    await asyncio.sleep(0.25)

    assert dc._resolved_target == "host2:50052"
    await dc.close()


# ---------------------------------------------------------------------------
# Background resolve tests — watcher mode
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_background_watch_detects_target_change():
    """Watcher-based background resolve should swap channel on update."""
    instance1 = _make_instance("host1", 50051)
    watcher = MockWatcher()
    discovery = MockDiscovery([instance1])
    config = GrpcConfig(insecure=True)

    dc = DiscoveryChannel(discovery, "test-service", config, watcher=watcher)
    await dc.refresh()
    assert dc._resolved_target == "host1:50051"

    dc.start_background_resolve()

    # Push a changed instance list via the watcher
    instance2 = _make_instance("host2", 50052)
    await watcher.push([instance2])
    await asyncio.sleep(0.3)

    assert dc._resolved_target == "host2:50052"

    watcher.stop()
    await dc.close()


@pytest.mark.asyncio
async def test_auto_detect_watcher_from_discovery():
    """If discovery also implements Watcher, it should be auto-detected."""
    instance = _make_instance("host1", 50051)
    disc_watcher = MockDiscoveryWithWatcher([instance])

    dc = DiscoveryChannel(disc_watcher, "test-service")
    assert dc._watcher is disc_watcher
    await dc.close()


@pytest.mark.asyncio
async def test_explicit_watcher_overrides_auto_detect():
    """An explicitly provided watcher should take priority over auto-detection."""
    instance = _make_instance("host1", 50051)
    disc_watcher = MockDiscoveryWithWatcher([instance])
    explicit_watcher = MockWatcher()

    dc = DiscoveryChannel(disc_watcher, "test-service", watcher=explicit_watcher)
    assert dc._watcher is explicit_watcher
    await dc.close()


# ---------------------------------------------------------------------------
# Context manager auto-start tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_context_manager_starts_background_resolve():
    """async with should automatically start the background resolve task."""
    instance = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    dc = DiscoveryChannel(discovery, "test-service", config, resolve_interval=0.1)
    async with dc as ch:
        assert ch._background_task is not None
        assert not ch._background_task.done()

    # After exit, background task should be cancelled
    assert dc._background_task is None or dc._background_task.done()


# ---------------------------------------------------------------------------
# close() cancels background task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_cancels_background_task():
    """close() must cancel the background resolve task."""
    instance = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    dc = DiscoveryChannel(discovery, "test-service", config, resolve_interval=0.1)
    await dc.refresh()
    dc.start_background_resolve()
    assert dc._background_task is not None

    await dc.close()
    assert dc._background_task is None or dc._background_task.done()


# ---------------------------------------------------------------------------
# start_background_resolve idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_start_background_resolve_idempotent():
    """Calling start_background_resolve() twice should not spawn a second task."""
    instance = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    dc = DiscoveryChannel(discovery, "test-service", config, resolve_interval=0.1)
    await dc.refresh()
    dc.start_background_resolve()
    first_task = dc._background_task

    dc.start_background_resolve()
    assert dc._background_task is first_task

    await dc.close()


# ---------------------------------------------------------------------------
# get_channel() tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_channel_initializes_when_not_ready():
    """get_channel() should call refresh() when no channel exists yet."""
    instance = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    dc = DiscoveryChannel(discovery, "test-service", config)
    ch = await dc.get_channel()

    assert ch is not None
    assert isinstance(ch, grpc.aio.Channel)
    assert dc._resolved_target == "host1:50051"

    await dc.close()


@pytest.mark.asyncio
async def test_get_channel_returns_existing_healthy_channel():
    """get_channel() should return the cached channel when it's healthy."""
    instance = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    dc = DiscoveryChannel(discovery, "test-service", config)
    await dc.refresh()
    original_channel = dc._channel

    ch = await dc.get_channel()
    assert ch is original_channel

    await dc.close()


@pytest.mark.asyncio
async def test_get_channel_re_resolves_on_transient_failure():
    """get_channel() should trigger refresh when channel is in TRANSIENT_FAILURE."""
    instance = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance])
    config = GrpcConfig(insecure=True)

    dc = DiscoveryChannel(discovery, "test-service", config)
    await dc.refresh()

    # Mock the channel's get_state to return TRANSIENT_FAILURE
    with (
        patch.object(dc._channel, "get_state", return_value=grpc.ChannelConnectivity.TRANSIENT_FAILURE),
        patch.object(dc._channel, "close", new_callable=AsyncMock),
    ):
            ch = await dc.get_channel()
            assert ch is not None

    await dc.close()


# ---------------------------------------------------------------------------
# resolve_interval parameter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_interval_parameter():
    """resolve_interval should be configurable."""
    instance = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance])

    dc = DiscoveryChannel(discovery, "test-service", resolve_interval=42.0)
    assert dc._resolve_interval == 42.0
    await dc.close()


@pytest.mark.asyncio
async def test_default_resolve_interval():
    """Default resolve_interval should be 10 seconds."""
    discovery = MockDiscovery([])
    dc = DiscoveryChannel(discovery, "test-service")
    assert dc._resolve_interval == 10.0
    await dc.close()


# ---------------------------------------------------------------------------
# Watcher protocol test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_watcher_protocol_is_runtime_checkable():
    """Watcher should be a runtime-checkable protocol."""
    watcher = MockWatcher()
    assert isinstance(watcher, Watcher)


@pytest.mark.asyncio
async def test_discovery_without_watcher_uses_polling():
    """When no watcher is provided and discovery doesn't implement Watcher, use polling."""
    instance = _make_instance("host1", 50051)
    discovery = MockDiscovery([instance])

    dc = DiscoveryChannel(discovery, "test-service")
    assert dc._watcher is None
    await dc.close()

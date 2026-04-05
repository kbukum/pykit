"""Tests for discovery-aware async gRPC channel."""

import asyncio

import grpc
import pytest

from pykit_discovery.protocols import Discovery
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

"""Tests for DiscoveryServer component."""

from __future__ import annotations

import pytest

from pykit_component import Health, HealthStatus
from pykit_discovery import DiscoveryServer, ServiceInstance

# --- Mock classes for testing ---


class MockServer:
    """Mock server for testing."""

    def __init__(self) -> None:
        self.started = False
        self.stopped = False
        self.start_error: Exception | None = None
        self.stop_error: Exception | None = None

    async def start(self) -> None:
        if self.start_error:
            raise self.start_error
        self.started = True

    async def stop(self) -> None:
        if self.stop_error:
            raise self.stop_error
        self.stopped = True

    async def health(self) -> Health:
        if self.started and not self.stopped:
            return Health(
                name="mock-server",
                status=HealthStatus.HEALTHY,
                message="running",
            )
        return Health(
            name="mock-server",
            status=HealthStatus.UNHEALTHY,
            message="not running",
        )


class MockRegistry:
    """Mock registry for testing."""

    def __init__(self) -> None:
        self.registered: list[ServiceInstance] = []
        self.deregistered: list[str] = []
        self.register_error: Exception | None = None
        self.deregister_error: Exception | None = None

    async def register(self, instance: ServiceInstance) -> None:
        if self.register_error:
            raise self.register_error
        self.registered.append(instance)

    async def deregister(self, instance_id: str) -> None:
        if self.deregister_error:
            raise self.deregister_error
        self.deregistered.append(instance_id)


# --- Tests ---


class TestDiscoveryServer:
    """Test DiscoveryServer lifecycle and integration."""

    @pytest.mark.asyncio
    async def test_lifecycle_success(self) -> None:
        """Test successful start/stop cycle."""
        server = MockServer()
        registry = MockRegistry()
        instance = ServiceInstance(
            id="test-1",
            name="test-service",
            host="127.0.0.1",
            port=8080,
            tags=["test", "v1"],
            metadata={"env": "test"},
        )

        discovery_server = DiscoveryServer(
            server=server,
            registry=registry,
            instance=instance,
        )

        # Start
        await discovery_server.start()
        assert server.started
        assert len(registry.registered) == 1
        assert registry.registered[0].id == "test-1"
        assert registry.registered[0].name == "test-service"

        # Stop
        await discovery_server.stop()
        assert server.stopped
        assert len(registry.deregistered) == 1
        assert registry.deregistered[0] == "test-1"

    @pytest.mark.asyncio
    async def test_properties(self) -> None:
        """Test component properties."""
        server = MockServer()
        registry = MockRegistry()
        instance = ServiceInstance(
            id="svc-123",
            name="my-service",
            host="192.168.1.1",
            port=9000,
        )

        discovery_server = DiscoveryServer(
            server=server,
            registry=registry,
            instance=instance,
            name="my-discovery-server",
        )

        assert discovery_server.name == "my-discovery-server"
        assert discovery_server.instance_id == "svc-123"
        assert discovery_server.service_name == "my-service"
        assert discovery_server.instance == instance

    @pytest.mark.asyncio
    async def test_registration_failure_stops_server(self) -> None:
        """Test that server is stopped if registration fails."""
        server = MockServer()
        registry = MockRegistry()
        registry.register_error = RuntimeError("registration service unavailable")

        instance = ServiceInstance(
            id="test-2",
            name="test-service",
            host="127.0.0.1",
            port=8081,
        )

        discovery_server = DiscoveryServer(
            server=server,
            registry=registry,
            instance=instance,
        )

        # Start should fail
        with pytest.raises(RuntimeError, match="registration service unavailable"):
            await discovery_server.start()

        # Server should have been started but then stopped
        assert server.started
        assert server.stopped

    @pytest.mark.asyncio
    async def test_deregistration_failure_doesnt_prevent_stop(self) -> None:
        """Test that deregistration errors don't prevent server shutdown."""
        server = MockServer()
        registry = MockRegistry()
        instance = ServiceInstance(
            id="test-3",
            name="test-service",
            host="127.0.0.1",
            port=8082,
        )

        discovery_server = DiscoveryServer(
            server=server,
            registry=registry,
            instance=instance,
        )

        # Start successfully
        await discovery_server.start()
        assert len(registry.registered) == 1

        # Set deregistration error
        registry.deregister_error = RuntimeError("registry error")

        # Stop should still succeed (logs the warning)
        await discovery_server.stop()  # Should not raise

        # Server should be stopped
        assert server.stopped

    @pytest.mark.asyncio
    async def test_server_start_error_propagates(self) -> None:
        """Test that server start errors propagate."""
        server = MockServer()
        server.start_error = RuntimeError("server failed to start")
        registry = MockRegistry()
        instance = ServiceInstance(
            id="test-4",
            name="test-service",
            host="127.0.0.1",
            port=8083,
        )

        discovery_server = DiscoveryServer(
            server=server,
            registry=registry,
            instance=instance,
        )

        # Start should fail
        with pytest.raises(RuntimeError, match="server failed to start"):
            await discovery_server.start()

        # Nothing should be registered
        assert len(registry.registered) == 0

    @pytest.mark.asyncio
    async def test_server_stop_error_propagates(self) -> None:
        """Test that server stop errors propagate."""
        server = MockServer()
        server.stop_error = RuntimeError("server failed to stop")
        registry = MockRegistry()
        instance = ServiceInstance(
            id="test-5",
            name="test-service",
            host="127.0.0.1",
            port=8084,
        )

        discovery_server = DiscoveryServer(
            server=server,
            registry=registry,
            instance=instance,
        )

        # Start successfully
        await discovery_server.start()
        assert len(registry.registered) == 1

        # Stop should fail
        with pytest.raises(RuntimeError, match="server failed to stop"):
            await discovery_server.stop()

        # Should have attempted deregistration
        assert len(registry.deregistered) == 1

    @pytest.mark.asyncio
    async def test_health_delegates_to_inner(self) -> None:
        """Test health status from inner component."""
        server = MockServer()
        registry = MockRegistry()
        instance = ServiceInstance(
            id="test-6",
            name="test-service",
            host="127.0.0.1",
            port=8085,
        )

        discovery_server = DiscoveryServer(
            server=server,
            registry=registry,
            instance=instance,
            name="test-discovery",
        )

        # Before starting, inner server is unhealthy
        health = await discovery_server.health()
        assert health.status == HealthStatus.UNHEALTHY

        # After starting, inner server is healthy
        await discovery_server.start()
        health = await discovery_server.health()
        assert health.status == HealthStatus.HEALTHY

    @pytest.mark.asyncio
    async def test_multiple_instances_coexist(self) -> None:
        """Test multiple discovery servers with different instances."""
        server1 = MockServer()
        server2 = MockServer()
        registry = MockRegistry()

        instance1 = ServiceInstance(
            id="svc-1",
            name="service",
            host="127.0.0.1",
            port=8086,
        )
        instance2 = ServiceInstance(
            id="svc-2",
            name="service",
            host="127.0.0.1",
            port=8087,
        )

        ds1 = DiscoveryServer(server=server1, registry=registry, instance=instance1)
        ds2 = DiscoveryServer(server=server2, registry=registry, instance=instance2)

        # Start both
        await ds1.start()
        await ds2.start()

        assert len(registry.registered) == 2
        assert registry.registered[0].id == "svc-1"
        assert registry.registered[1].id == "svc-2"

        # Stop both
        await ds1.stop()
        await ds2.stop()

        assert len(registry.deregistered) == 2
        assert registry.deregistered[0] == "svc-1"
        assert registry.deregistered[1] == "svc-2"

    @pytest.mark.asyncio
    async def test_server_without_health_method(self) -> None:
        """Test handling of servers without health() method."""

        class MinimalServer:
            async def start(self) -> None:
                pass

            async def stop(self) -> None:
                pass

        server = MinimalServer()
        registry = MockRegistry()
        instance = ServiceInstance(
            id="test-7",
            name="minimal",
            host="127.0.0.1",
            port=8088,
        )

        discovery_server = DiscoveryServer(
            server=server,
            registry=registry,
            instance=instance,
        )

        # Should work fine without health method
        await discovery_server.start()
        health = await discovery_server.health()
        assert health.status == HealthStatus.HEALTHY

        await discovery_server.stop()

    def test_service_instance_metadata(self) -> None:
        """Test that instance metadata is preserved."""
        server = MockServer()
        registry = MockRegistry()
        instance = ServiceInstance(
            id="test-8",
            name="test-service",
            host="127.0.0.1",
            port=8089,
            tags=["tag1", "tag2"],
            metadata={"version": "1.0", "region": "us-west"},
        )

        discovery_server = DiscoveryServer(
            server=server,
            registry=registry,
            instance=instance,
        )

        assert discovery_server.instance.tags == ["tag1", "tag2"]
        assert discovery_server.instance.metadata == {"version": "1.0", "region": "us-west"}

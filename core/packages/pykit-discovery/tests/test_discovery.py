"""Tests for pykit-discovery."""

from __future__ import annotations

import pytest

from pykit_discovery import (
    Discovery,
    DiscoveryComponent,
    LoadBalancer,
    RandomStrategy,
    Registry,
    RoundRobinStrategy,
    ServiceInstance,
    StaticProvider,
)

# --- ServiceInstance ---


class TestServiceInstance:
    def test_basic_fields(self) -> None:
        inst = ServiceInstance(id="s1", name="svc", host="10.0.0.1", port=8080)
        assert inst.id == "s1"
        assert inst.name == "svc"
        assert inst.host == "10.0.0.1"
        assert inst.port == 8080
        assert inst.metadata == {}
        assert inst.healthy is True

    def test_address_property(self) -> None:
        inst = ServiceInstance(id="s1", name="svc", host="10.0.0.1", port=8080)
        assert inst.address == "10.0.0.1:8080"

    def test_url_default_scheme(self) -> None:
        inst = ServiceInstance(id="s1", name="svc", host="10.0.0.1", port=8080)
        assert inst.url() == "http://10.0.0.1:8080"

    def test_url_custom_scheme(self) -> None:
        inst = ServiceInstance(id="s1", name="svc", host="10.0.0.1", port=443)
        assert inst.url("https") == "https://10.0.0.1:443"

    def test_metadata(self) -> None:
        inst = ServiceInstance(id="s1", name="svc", host="h", port=80, metadata={"env": "prod"})
        assert inst.metadata == {"env": "prod"}

    def test_unhealthy(self) -> None:
        inst = ServiceInstance(id="s1", name="svc", host="h", port=80, healthy=False)
        assert inst.healthy is False


# --- StaticProvider ---


class TestStaticProvider:
    @pytest.fixture()
    def provider(self) -> StaticProvider:
        return StaticProvider()

    @pytest.fixture()
    def instance(self) -> ServiceInstance:
        return ServiceInstance(id="a1", name="api", host="10.0.0.1", port=8080)

    @pytest.mark.asyncio()
    async def test_register_and_discover(self, provider: StaticProvider, instance: ServiceInstance) -> None:
        await provider.register(instance)
        result = await provider.discover("api")
        assert len(result) == 1
        assert result[0].id == "a1"

    @pytest.mark.asyncio()
    async def test_discover_empty(self, provider: StaticProvider) -> None:
        result = await provider.discover("nonexistent")
        assert result == []

    @pytest.mark.asyncio()
    async def test_deregister(self, provider: StaticProvider, instance: ServiceInstance) -> None:
        await provider.register(instance)
        await provider.deregister("a1")
        result = await provider.discover("api")
        assert result == []

    @pytest.mark.asyncio()
    async def test_discover_filters_unhealthy(self, provider: StaticProvider) -> None:
        healthy = ServiceInstance(id="h1", name="api", host="10.0.0.1", port=8080, healthy=True)
        unhealthy = ServiceInstance(id="u1", name="api", host="10.0.0.2", port=8080, healthy=False)
        await provider.register(healthy)
        await provider.register(unhealthy)
        result = await provider.discover("api")
        assert len(result) == 1
        assert result[0].id == "h1"

    @pytest.mark.asyncio()
    async def test_multiple_services(self, provider: StaticProvider) -> None:
        a = ServiceInstance(id="a1", name="api", host="h", port=80)
        b = ServiceInstance(id="b1", name="web", host="h", port=81)
        await provider.register(a)
        await provider.register(b)
        assert len(await provider.discover("api")) == 1
        assert len(await provider.discover("web")) == 1

    @pytest.mark.asyncio()
    async def test_protocol_conformance(self, provider: StaticProvider) -> None:
        assert isinstance(provider, Discovery)
        assert isinstance(provider, Registry)


# --- Load Balancing Strategies ---


class TestRoundRobinStrategy:
    def test_cycles_through_instances(self) -> None:
        instances = [ServiceInstance(id=f"s{i}", name="svc", host="h", port=80 + i) for i in range(3)]
        rr = RoundRobinStrategy()
        selected = [rr.select(instances).id for _ in range(6)]
        assert selected == ["s0", "s1", "s2", "s0", "s1", "s2"]

    def test_empty_raises(self) -> None:
        rr = RoundRobinStrategy()
        with pytest.raises(ValueError, match="no instances"):
            rr.select([])

    def test_protocol_conformance(self) -> None:
        assert isinstance(RoundRobinStrategy(), LoadBalancer)


class TestRandomStrategy:
    def test_selects_from_instances(self) -> None:
        instances = [ServiceInstance(id=f"s{i}", name="svc", host="h", port=80 + i) for i in range(5)]
        strategy = RandomStrategy()
        ids = {strategy.select(instances).id for _ in range(50)}
        # With 50 picks from 5 instances, we should hit at least 2
        assert len(ids) >= 2

    def test_empty_raises(self) -> None:
        strategy = RandomStrategy()
        with pytest.raises(ValueError, match="no instances"):
            strategy.select([])

    def test_protocol_conformance(self) -> None:
        assert isinstance(RandomStrategy(), LoadBalancer)


# --- DiscoveryComponent ---


class TestDiscoveryComponent:
    @pytest.mark.asyncio()
    async def test_lifecycle(self) -> None:
        comp = DiscoveryComponent()
        assert comp.name == "discovery"

        health = await comp.health()
        assert health.status.value == "unhealthy"

        await comp.start()
        health = await comp.health()
        assert health.status.value == "healthy"

        await comp.stop()
        health = await comp.health()
        assert health.status.value == "unhealthy"

    @pytest.mark.asyncio()
    async def test_register_discover(self) -> None:
        comp = DiscoveryComponent()
        await comp.start()
        inst = ServiceInstance(id="x1", name="svc", host="h", port=80)
        await comp.register(inst)
        result = await comp.discover("svc")
        assert len(result) == 1
        assert result[0].id == "x1"
        await comp.stop()

    @pytest.mark.asyncio()
    async def test_deregister(self) -> None:
        comp = DiscoveryComponent()
        await comp.start()
        inst = ServiceInstance(id="x1", name="svc", host="h", port=80)
        await comp.register(inst)
        await comp.deregister("x1")
        result = await comp.discover("svc")
        assert result == []
        await comp.stop()

    @pytest.mark.asyncio()
    async def test_discovery_and_registry_properties(self) -> None:
        comp = DiscoveryComponent()
        assert isinstance(comp.discovery, Discovery)
        assert isinstance(comp.registry, Registry)

    @pytest.mark.asyncio()
    async def test_custom_provider(self) -> None:
        provider = StaticProvider()
        comp = DiscoveryComponent(provider=provider)
        inst = ServiceInstance(id="p1", name="svc", host="h", port=80)
        await provider.register(inst)
        result = await comp.discover("svc")
        assert len(result) == 1

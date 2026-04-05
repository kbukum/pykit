"""Extended tests for pykit-discovery — edge cases and deeper coverage."""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

import pytest

from pykit_discovery import (
    Discovery,
    DiscoveryComponent,
    LeastConnectionsStrategy,
    LoadBalancer,
    RandomStrategy,
    Registry,
    RoundRobinStrategy,
    ServiceInstance,
    StaticProvider,
)


# ── ServiceInstance extended ─────────────────────────────────────────


class TestServiceInstanceExtended:
    def test_endpoint_property(self) -> None:
        inst = ServiceInstance(id="e1", name="svc", host="10.0.0.1", port=8080)
        assert inst.endpoint == "10.0.0.1:8080"
        assert inst.endpoint == inst.address

    def test_url_grpcs_scheme(self) -> None:
        inst = ServiceInstance(id="e1", name="svc", host="10.0.0.1", port=443)
        assert inst.url("grpcs") == "grpcs://10.0.0.1:443"

    def test_tags_and_metadata(self) -> None:
        inst = ServiceInstance(
            id="t1",
            name="svc",
            host="h",
            port=80,
            tags=["canary", "us-east-1"],
            metadata={"version": "2.1", "env": "staging"},
        )
        assert "canary" in inst.tags
        assert inst.metadata["version"] == "2.1"
        assert len(inst.tags) == 2

    def test_default_protocol(self) -> None:
        inst = ServiceInstance(id="p1", name="svc", host="h", port=80)
        assert inst.protocol == "grpc"

    def test_custom_protocol(self) -> None:
        inst = ServiceInstance(id="p1", name="svc", host="h", port=80, protocol="http")
        assert inst.protocol == "http"

    def test_default_weight(self) -> None:
        inst = ServiceInstance(id="w1", name="svc", host="h", port=80)
        assert inst.weight == 1

    def test_custom_weight(self) -> None:
        inst = ServiceInstance(id="w1", name="svc", host="h", port=80, weight=10)
        assert inst.weight == 10


# ── StaticProvider extended ──────────────────────────────────────────


class TestStaticProviderExtended:
    @pytest.fixture()
    def provider(self) -> StaticProvider:
        return StaticProvider()

    @pytest.mark.asyncio()
    async def test_discover_unknown_service_returns_empty(self, provider: StaticProvider) -> None:
        result = await provider.discover("nonexistent-service")
        assert result == []

    @pytest.mark.asyncio()
    async def test_register_multiple_same_service(self, provider: StaticProvider) -> None:
        for i in range(5):
            inst = ServiceInstance(id=f"inst-{i}", name="svc", host="10.0.0.1", port=8080 + i)
            await provider.register(inst)
        result = await provider.discover("svc")
        assert len(result) == 5

    @pytest.mark.asyncio()
    async def test_deregister_nonexistent_no_error(self, provider: StaticProvider) -> None:
        # Should not raise
        await provider.deregister("does-not-exist")

    @pytest.mark.asyncio()
    async def test_discover_all_unhealthy_returns_empty(self, provider: StaticProvider) -> None:
        u1 = ServiceInstance(id="u1", name="svc", host="h", port=80, healthy=False)
        u2 = ServiceInstance(id="u2", name="svc", host="h", port=81, healthy=False)
        await provider.register(u1)
        await provider.register(u2)
        result = await provider.discover("svc")
        assert result == []

    @pytest.mark.asyncio()
    async def test_register_deregister_lifecycle(self, provider: StaticProvider) -> None:
        inst = ServiceInstance(id="lc1", name="api", host="10.0.0.1", port=8080)
        await provider.register(inst)
        assert len(await provider.discover("api")) == 1

        await provider.deregister("lc1")
        assert await provider.discover("api") == []

    @pytest.mark.asyncio()
    async def test_concurrent_discover_calls(self, provider: StaticProvider) -> None:
        for i in range(10):
            inst = ServiceInstance(id=f"c{i}", name="svc", host="h", port=80 + i)
            await provider.register(inst)

        results = await asyncio.gather(
            *[provider.discover("svc") for _ in range(20)]
        )
        for result in results:
            assert len(result) == 10


# ── RoundRobinStrategy extended ──────────────────────────────────────


class TestRoundRobinStrategyExtended:
    def test_single_instance(self) -> None:
        instances = [ServiceInstance(id="only", name="svc", host="h", port=80)]
        rr = RoundRobinStrategy()
        for _ in range(10):
            assert rr.select(instances).id == "only"

    def test_wraps_around(self) -> None:
        instances = [ServiceInstance(id=f"s{i}", name="svc", host="h", port=80 + i) for i in range(3)]
        rr = RoundRobinStrategy()
        # Go through two full cycles
        expected = ["s0", "s1", "s2", "s0", "s1", "s2"]
        actual = [rr.select(instances).id for _ in range(6)]
        assert actual == expected


# ── RandomStrategy extended ──────────────────────────────────────────


class TestRandomStrategyExtended:
    def test_single_instance(self) -> None:
        instances = [ServiceInstance(id="only", name="svc", host="h", port=80)]
        strategy = RandomStrategy()
        for _ in range(10):
            assert strategy.select(instances).id == "only"


# ── LeastConnectionsStrategy ────────────────────────────────────────


class TestLeastConnectionsStrategy:
    def test_prefers_idle(self) -> None:
        instances = [
            ServiceInstance(id="busy", name="svc", host="h", port=80),
            ServiceInstance(id="idle", name="svc", host="h", port=81),
        ]
        lcs = LeastConnectionsStrategy()
        lcs.acquire("busy")
        lcs.acquire("busy")
        lcs.acquire("idle")

        selected = lcs.select(instances)
        assert selected.id == "idle"

    def test_empty_raises(self) -> None:
        lcs = LeastConnectionsStrategy()
        with pytest.raises(ValueError):
            lcs.select([])

    def test_acquire_release(self) -> None:
        instances = [
            ServiceInstance(id="a", name="svc", host="h", port=80),
            ServiceInstance(id="b", name="svc", host="h", port=81),
        ]
        lcs = LeastConnectionsStrategy()
        lcs.acquire("a")
        lcs.acquire("a")
        lcs.acquire("a")
        lcs.release("a")
        lcs.release("a")
        # a has 1 in-flight, b has 0
        assert lcs.select(instances).id == "b"

    def test_protocol_conformance(self) -> None:
        assert isinstance(LeastConnectionsStrategy(), LoadBalancer)

    def test_release_below_zero(self) -> None:
        lcs = LeastConnectionsStrategy()
        # Releasing a non-acquired instance should not crash
        lcs.release("nonexistent")
        # Count stays at 0
        instances = [ServiceInstance(id="nonexistent", name="svc", host="h", port=80)]
        assert lcs.select(instances).id == "nonexistent"


# ── DiscoveryComponent extended ──────────────────────────────────────


class TestDiscoveryComponentExtended:
    @pytest.mark.asyncio()
    async def test_health_before_start(self) -> None:
        comp = DiscoveryComponent()
        health = await comp.health()
        assert health.status.value == "unhealthy"
        assert "not started" in health.message

    @pytest.mark.asyncio()
    async def test_health_after_start(self) -> None:
        comp = DiscoveryComponent()
        await comp.start()
        health = await comp.health()
        assert health.status.value == "healthy"
        assert "running" in health.message
        await comp.stop()

    @pytest.mark.asyncio()
    async def test_start_stop_start(self) -> None:
        comp = DiscoveryComponent()
        await comp.start()
        await comp.stop()
        await comp.start()
        health = await comp.health()
        assert health.status.value == "healthy"
        await comp.stop()

    @pytest.mark.asyncio()
    async def test_name_property(self) -> None:
        comp = DiscoveryComponent()
        assert comp.name == "discovery"

    @pytest.mark.asyncio()
    async def test_discovery_and_registry_protocols(self) -> None:
        comp = DiscoveryComponent()
        assert isinstance(comp.discovery, Discovery)
        assert isinstance(comp.registry, Registry)


# ── Large number of instances ────────────────────────────────────────


class TestLargeScale:
    @pytest.mark.asyncio()
    async def test_many_instances(self) -> None:
        provider = StaticProvider()
        for i in range(500):
            inst = ServiceInstance(
                id=f"inst-{i}",
                name="svc",
                host=f"10.0.{i // 256}.{i % 256}",
                port=8080,
            )
            await provider.register(inst)
        result = await provider.discover("svc")
        assert len(result) == 500

    def test_round_robin_many_instances(self) -> None:
        instances = [
            ServiceInstance(id=f"s{i}", name="svc", host="h", port=80 + i)
            for i in range(100)
        ]
        rr = RoundRobinStrategy()
        # Pick all 100, then verify wrap-around
        ids = [rr.select(instances).id for _ in range(200)]
        assert ids[:100] == [f"s{i}" for i in range(100)]
        assert ids[100:200] == [f"s{i}" for i in range(100)]

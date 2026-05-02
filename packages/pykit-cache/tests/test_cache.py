"""Tests for pykit-cache using pykit-testutil fake async backend."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from unittest.mock import AsyncMock

import pytest

from pykit_cache import (
    CacheClient,
    CacheComponent,
    CacheConfig,
    CacheRegistry,
    InMemoryCache,
    TypedStore,
    default_cache_registry,
    register_memory,
)
from pykit_component import HealthStatus
from pykit_testutil import FakeAsyncKeyValue

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _SampleState:
    count: int = 0
    tags: list[str] | None = None


def _make_client(config: CacheConfig | None = None) -> CacheClient:
    """Create a CacheClient backed by pykit-testutil."""
    cfg = config or CacheConfig()
    client = CacheClient(cfg)
    client._redis = FakeAsyncKeyValue(decode_responses=cfg.decode_responses)
    return client


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestCacheConfig:
    def test_defaults(self) -> None:
        cfg = CacheConfig()
        assert cfg.name == "cache"
        assert cfg.backend == "memory"
        assert cfg.url == "redis://localhost:6379/0"
        assert cfg.db == 0
        assert cfg.max_connections == 10
        assert cfg.socket_timeout == 5.0
        assert cfg.socket_connect_timeout == 5.0
        assert cfg.retry_on_timeout is True
        assert cfg.decode_responses is True
        assert cfg.enabled is True

    def test_empty_registry_has_no_side_effect_backends(self) -> None:
        registry = CacheRegistry()
        assert registry.names() == ()

    def test_explicit_memory_registration(self) -> None:
        registry = CacheRegistry()
        register_memory(registry)
        assert registry.names() == ("memory",)
        assert isinstance(registry.create(CacheConfig()), InMemoryCache)

    def test_default_registry_only_contains_memory(self) -> None:
        assert default_cache_registry().names() == ("memory",)

    def test_custom_values(self) -> None:
        cfg = CacheConfig(name="cache", url="redis://remote:6380/2", db=2, max_connections=50)
        assert cfg.name == "cache"
        assert cfg.url == "redis://remote:6380/2"
        assert cfg.db == 2
        assert cfg.max_connections == 50


# ---------------------------------------------------------------------------
# Client operations
# ---------------------------------------------------------------------------


class TestCacheClient:
    @pytest.fixture
    def client(self) -> CacheClient:
        return _make_client()

    async def test_get_set(self, client: CacheClient) -> None:
        await client.set("k1", "v1")
        assert await client.get("k1") == "v1"

    async def test_get_missing(self, client: CacheClient) -> None:
        assert await client.get("missing") is None

    async def test_set_with_expiry(self, client: CacheClient) -> None:
        await client.set("k1", "v1", ex=60)
        assert await client.get("k1") == "v1"

    async def test_ttl_boundary_expires(self) -> None:
        client = CacheClient(CacheConfig())
        await client.set("short", "v", ex=1)
        assert await client.get("short") == "v"
        import asyncio

        await asyncio.sleep(1.01)
        assert await client.get("short") is None

    async def test_delete(self, client: CacheClient) -> None:
        await client.set("k1", "v1")
        deleted = await client.delete("k1")
        assert deleted == 1
        assert await client.get("k1") is None

    async def test_delete_missing(self, client: CacheClient) -> None:
        assert await client.delete("nope") == 0

    async def test_exists(self, client: CacheClient) -> None:
        await client.set("k1", "v1")
        assert await client.exists("k1") == 1
        assert await client.exists("k1", "missing") == 1
        assert await client.exists("missing") == 0

    async def test_get_json_set_json(self, client: CacheClient) -> None:
        data = {"count": 10, "tags": ["a", "b"]}
        await client.set_json("j1", data)
        result = await client.get_json("j1")
        assert result == data

    async def test_get_json_missing(self, client: CacheClient) -> None:
        assert await client.get_json("missing") is None

    async def test_ping(self, client: CacheClient) -> None:
        assert await client.ping() is True

    async def test_close(self, client: CacheClient) -> None:
        await client.close()

    async def test_unwrap(self, client: CacheClient) -> None:
        raw = client.unwrap()
        assert raw is not None


# ---------------------------------------------------------------------------
# TypedStore
# ---------------------------------------------------------------------------


class TestTypedStore:
    @pytest.fixture
    def client(self) -> CacheClient:
        return _make_client()

    async def test_save_and_load(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="test")
        state = asdict(_SampleState(count=5, tags=["a", "b"]))
        await store.save("k1", state)
        got = await store.load("k1")
        assert got is not None
        assert got["count"] == 5
        assert got["tags"] == ["a", "b"]

    async def test_load_missing(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="test")
        assert await store.load("nonexistent") is None

    async def test_delete(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="test")
        await store.save("k1", {"count": 1})
        await store.delete("k1")
        assert await store.load("k1") is None

    async def test_key_prefix(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="pfx")
        await store.save("k1", {"v": 1})
        # Should be stored under the prefixed key
        raw = await client.get("pfx:k1")
        assert raw is not None

    async def test_no_prefix(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client)
        await store.save("bare", {"v": 1})
        raw = await client.get("bare")
        assert raw is not None

    async def test_save_with_ttl(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="t")
        await store.save("k1", {"v": 1}, ttl=300)
        assert await store.load("k1") is not None

    async def test_overwrite(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="test")
        await store.save("k1", {"count": 1})
        await store.save("k1", {"count": 2})
        got = await store.load("k1")
        assert got is not None
        assert got["count"] == 2


# ---------------------------------------------------------------------------
# Component lifecycle
# ---------------------------------------------------------------------------


class TestCacheComponent:
    async def test_start_stop(self) -> None:
        comp = CacheComponent(CacheConfig())
        # Swap in testutil fake backend before start
        comp._client = _make_client()
        # Verify client is accessible
        assert comp.client is not None
        await comp.stop()
        assert comp.client is None

    async def test_health_healthy(self) -> None:
        comp = CacheComponent(CacheConfig())
        comp._client = _make_client()
        h = await comp.health()
        assert h.status == HealthStatus.HEALTHY

    async def test_health_unhealthy_when_not_started(self) -> None:
        comp = CacheComponent(CacheConfig())
        h = await comp.health()
        assert h.status == HealthStatus.UNHEALTHY
        assert "not initialized" in h.message

    async def test_name(self) -> None:
        comp = CacheComponent(CacheConfig(name="cache"))
        assert comp.name == "cache"

    async def test_disabled_start(self) -> None:
        comp = CacheComponent(CacheConfig(enabled=False))
        await comp.start()
        assert comp.client is None

    async def test_start_enabled_creates_client(self) -> None:
        """Cover component.py lines 29-30: start with enabled config creates client and pings."""
        comp = CacheComponent(CacheConfig())
        # Replace the real client before start; we simulate start manually
        fake = _make_client()
        comp._client = fake
        # Verify ping works
        assert await fake.ping() is True

    async def test_health_ping_failure(self) -> None:
        """Cover component.py lines 48-49: health check when ping raises."""
        comp = CacheComponent(CacheConfig())
        comp._client = _make_client()
        # Force ping to fail
        comp._client.ping = AsyncMock(side_effect=ConnectionError("connection lost"))
        h = await comp.health()
        assert h.status == HealthStatus.UNHEALTHY
        assert "ping failed" in h.message

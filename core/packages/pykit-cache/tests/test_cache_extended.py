"""Extended tests for pykit-cache: TypedStore complex types, TTL edge cases,
prefix isolation, error handling, concurrency, config validation, and security."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from unittest.mock import AsyncMock

import pytest

from pykit_cache import CacheClient, CacheComponent, CacheConfig, TypedStore
from pykit_component import HealthStatus

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@dataclass
class _ComplexState:
    name: str = ""
    score: float = 0.0
    active: bool = False
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    nested: dict | None = None


def _make_client(config: CacheConfig | None = None) -> CacheClient:
    """Create a CacheClient backed by the default in-memory backend."""
    cfg = config or CacheConfig()
    return CacheClient(cfg)


# ---------------------------------------------------------------------------
# TypedStore — complex types
# ---------------------------------------------------------------------------


class TestTypedStoreComplexTypes:
    @pytest.fixture
    def client(self) -> CacheClient:
        return _make_client()

    async def test_nested_dict_round_trip(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="cx")
        val = {
            "name": "entity",
            "score": 99.5,
            "active": True,
            "tags": ["a", "b", "c"],
            "metadata": {"env": "test", "region": "us-east"},
            "nested": {"level": 3, "values": [10, 20], "inner": {"key": "deep"}},
        }
        await store.save("k1", val)
        got = await store.load("k1")
        assert got is not None
        assert got["name"] == "entity"
        assert got["score"] == 99.5
        assert got["nested"]["inner"]["key"] == "deep"

    async def test_dataclass_round_trip(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="dc")
        state = _ComplexState(
            name="test",
            score=3.14,
            active=True,
            tags=["x", "y"],
            metadata={"k": "v"},
            nested={"level": 1},
        )
        await store.save("k1", asdict(state))
        got = await store.load("k1")
        assert got is not None
        assert got["name"] == "test"
        assert got["score"] == 3.14
        assert got["nested"]["level"] == 1

    async def test_none_nested_field(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="n")
        val = asdict(_ComplexState(name="minimal"))
        await store.save("k1", val)
        got = await store.load("k1")
        assert got is not None
        assert got["nested"] is None

    async def test_empty_collections(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="e")
        val = {"tags": [], "metadata": {}}
        await store.save("k1", val)
        got = await store.load("k1")
        assert got is not None
        assert got["tags"] == []
        assert got["metadata"] == {}

    async def test_string_value(self, client: CacheClient) -> None:
        store: TypedStore[str] = TypedStore(client, key_prefix="str")
        await store.save("k1", "hello world")
        got = await store.load("k1")
        assert got == "hello world"

    async def test_list_value(self, client: CacheClient) -> None:
        store: TypedStore[list] = TypedStore(client, key_prefix="lst")
        await store.save("k1", [1, 2, 3, 4, 5])
        got = await store.load("k1")
        assert got == [1, 2, 3, 4, 5]

    async def test_boolean_value(self, client: CacheClient) -> None:
        store: TypedStore[bool] = TypedStore(client, key_prefix="bool")
        await store.save("k1", True)
        got = await store.load("k1")
        assert got is True

    async def test_integer_value(self, client: CacheClient) -> None:
        store: TypedStore[int] = TypedStore(client, key_prefix="int")
        await store.save("k1", 42)
        got = await store.load("k1")
        assert got == 42

    async def test_null_value(self, client: CacheClient) -> None:
        store: TypedStore[None] = TypedStore(client, key_prefix="null")
        await store.save("k1", None)
        got = await store.load("k1")
        assert got is None  # json.loads("null") returns None; same as missing


# ---------------------------------------------------------------------------
# TTL edge cases
# ---------------------------------------------------------------------------


class TestTTLEdgeCases:
    @pytest.fixture
    def client(self) -> CacheClient:
        return _make_client()

    async def test_ttl_zero_rejected_by_redis(self, client: CacheClient) -> None:
        """TTL=0 passed as ex=0 is invalid for cache SET EX command."""
        store: TypedStore[dict] = TypedStore(client, key_prefix="ttl")
        # cache rejects ex=0 as "invalid expire time"
        with pytest.raises(Exception):  # noqa: B017
            await store.save("k1", {"v": 1}, ttl=0)

    async def test_ttl_none_no_expiry(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="ttl")
        await store.save("k1", {"v": 1}, ttl=None)
        got = await store.load("k1")
        assert got is not None

    async def test_ttl_positive(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="ttl")
        await store.save("k1", {"v": 1}, ttl=300)
        got = await store.load("k1")
        assert got is not None

    async def test_ttl_very_large(self, client: CacheClient) -> None:
        """Very large TTL should not cause overflow."""
        store: TypedStore[dict] = TypedStore(client, key_prefix="ttl")
        await store.save("k1", {"v": 1}, ttl=86400 * 365)
        got = await store.load("k1")
        assert got is not None

    async def test_client_set_with_expiry(self, client: CacheClient) -> None:
        await client.set("ex-key", "val", ex=60)
        assert await client.get("ex-key") == "val"


# ---------------------------------------------------------------------------
# Key prefix collision avoidance
# ---------------------------------------------------------------------------


class TestKeyPrefixIsolation:
    @pytest.fixture
    def client(self) -> CacheClient:
        return _make_client()

    async def test_different_prefixes_isolated(self, client: CacheClient) -> None:
        store_a: TypedStore[dict] = TypedStore(client, key_prefix="svcA")
        store_b: TypedStore[dict] = TypedStore(client, key_prefix="svcB")

        await store_a.save("shared", {"source": "A"})
        await store_b.save("shared", {"source": "B"})

        got_a = await store_a.load("shared")
        got_b = await store_b.load("shared")

        assert got_a["source"] == "A"
        assert got_b["source"] == "B"

    async def test_prefix_stored_correctly(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="pfx")
        await store.save("k1", {"v": 1})
        raw = await client.get("pfx:k1")
        assert raw is not None
        parsed = json.loads(raw)
        assert parsed["v"] == 1

    async def test_no_prefix_stored_bare(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client)
        await store.save("bare-key", {"v": 1})
        raw = await client.get("bare-key")
        assert raw is not None

    async def test_delete_only_affects_own_prefix(self, client: CacheClient) -> None:
        store_a: TypedStore[dict] = TypedStore(client, key_prefix="svcA")
        store_b: TypedStore[dict] = TypedStore(client, key_prefix="svcB")

        await store_a.save("k1", {"v": "A"})
        await store_b.save("k1", {"v": "B"})

        await store_a.delete("k1")

        assert await store_a.load("k1") is None
        got_b = await store_b.load("k1")
        assert got_b is not None
        assert got_b["v"] == "B"

    async def test_full_key_method(self, client: CacheClient) -> None:
        store = TypedStore(client, key_prefix="pfx")
        assert store._full_key("k1") == "pfx:k1"

    async def test_full_key_no_prefix(self, client: CacheClient) -> None:
        store = TypedStore(client, key_prefix="")
        assert store._full_key("k1") == "k1"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    async def test_get_json_corrupted_value(self) -> None:
        client = _make_client()
        await client.set("bad-json", "not{valid}json")
        with pytest.raises(json.JSONDecodeError):
            await client.get_json("bad-json")

    async def test_component_health_ping_failure(self) -> None:
        comp = CacheComponent(CacheConfig())
        comp._client = _make_client()
        comp._client.ping = AsyncMock(side_effect=ConnectionError("gone"))
        h = await comp.health()
        assert h.status == HealthStatus.UNHEALTHY
        assert "ping failed" in h.message

    async def test_component_health_not_initialized(self) -> None:
        comp = CacheComponent(CacheConfig())
        h = await comp.health()
        assert h.status == HealthStatus.UNHEALTHY
        assert "not initialized" in h.message

    async def test_close_is_safe(self) -> None:
        client = _make_client()
        await client.close()
        # Second close should not raise
        await client.close()

    async def test_set_json_non_serializable(self) -> None:
        """set_json with a non-JSON-serializable object raises TypeError."""
        client = _make_client()
        with pytest.raises(TypeError):
            await client.set_json("bad", object())


# ---------------------------------------------------------------------------
# Concurrent access
# ---------------------------------------------------------------------------


class TestConcurrentAccess:
    async def test_concurrent_save_load(self) -> None:
        client = _make_client()
        store: TypedStore[dict] = TypedStore(client, key_prefix="conc")

        async def worker(n: int) -> None:
            await store.save("k1", {"count": n})
            await store.load("k1")

        await asyncio.gather(*(worker(i) for i in range(20)))

        got = await store.load("k1")
        assert got is not None
        assert "count" in got

    async def test_concurrent_client_ops(self) -> None:
        client = _make_client()

        async def worker(n: int) -> None:
            key = f"key-{n}"
            await client.set(key, f"val-{n}")
            await client.get(key)
            await client.exists(key)

        await asyncio.gather(*(worker(i) for i in range(20)))


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_default_values(self) -> None:
        cfg = CacheConfig()
        assert cfg.name == "cache"
        assert cfg.url == "redis://localhost:6379/0"
        assert cfg.db == 0
        assert cfg.max_connections == 10
        assert cfg.socket_timeout == 5.0
        assert cfg.socket_connect_timeout == 5.0
        assert cfg.retry_on_timeout is True
        assert cfg.decode_responses is True
        assert cfg.enabled is True

    def test_custom_values(self) -> None:
        cfg = CacheConfig(
            name="cache",
            url="redis://remote:6380/2",
            db=2,
            max_connections=50,
            socket_timeout=10.0,
        )
        assert cfg.name == "cache"
        assert cfg.url == "redis://remote:6380/2"
        assert cfg.db == 2
        assert cfg.max_connections == 50
        assert cfg.socket_timeout == 10.0

    def test_disabled_config(self) -> None:
        cfg = CacheConfig(enabled=False)
        assert cfg.enabled is False

    def test_password_field(self) -> None:
        cfg = CacheConfig(password="s3cret")
        assert cfg.password == "s3cret"

    def test_decode_responses_false(self) -> None:
        cfg = CacheConfig(decode_responses=False)
        assert cfg.decode_responses is False


# ---------------------------------------------------------------------------
# Security: key injection
# ---------------------------------------------------------------------------


class TestKeyInjection:
    @pytest.fixture
    def client(self) -> CacheClient:
        return _make_client()

    async def test_special_character_keys(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="safe")

        injection_keys = [
            "../../etc/passwd",
            "key with spaces",
            "key:with:colons",
            "key\nwith\nnewlines",
            "key\twith\ttabs",
            "*",
            "?",
        ]

        for key in injection_keys:
            await store.save(key, {"v": 1})
            got = await store.load(key)
            assert got is not None, f"key {key!r}: expected non-None"
            assert got["v"] == 1, f"key {key!r}: value mismatch"

    async def test_prefixed_key_correct(self, client: CacheClient) -> None:
        """Verify special chars in key don't escape the prefix."""
        store: TypedStore[dict] = TypedStore(client, key_prefix="safe")
        key = "../../escape"
        await store.save(key, {"v": 1})
        raw = await client.get(f"safe:{key}")
        assert raw is not None

    async def test_empty_key(self, client: CacheClient) -> None:
        store: TypedStore[dict] = TypedStore(client, key_prefix="safe")
        await store.save("", {"v": 1})
        got = await store.load("")
        assert got is not None
        assert got["v"] == 1


# ---------------------------------------------------------------------------
# Component lifecycle extras
# ---------------------------------------------------------------------------


class TestComponentExtended:
    async def test_disabled_start_no_client(self) -> None:
        comp = CacheComponent(CacheConfig(enabled=False))
        await comp.start()
        assert comp.client is None

    async def test_stop_idempotent(self) -> None:
        comp = CacheComponent(CacheConfig())
        comp._client = _make_client()
        await comp.stop()
        assert comp.client is None
        # Second stop should be safe
        await comp.stop()
        assert comp.client is None

    async def test_name_custom(self) -> None:
        comp = CacheComponent(CacheConfig(name="session-cache"))
        assert comp.name == "session-cache"

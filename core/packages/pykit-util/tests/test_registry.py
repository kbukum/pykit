"""Tests for pykit_util Registry."""

import pytest

from pykit_util import Registry


class TestRegistry:
    @pytest.fixture
    def registry(self) -> Registry[str, int]:
        return Registry()

    def test_register_sync_and_get(self, registry: Registry[str, int]) -> None:
        registry.register_sync("a", 1)
        assert registry.get("a") == 1

    def test_get_missing(self, registry: Registry[str, int]) -> None:
        assert registry.get("missing") is None

    def test_get_or_raise(self, registry: Registry[str, int]) -> None:
        registry.register_sync("a", 1)
        assert registry.get_or_raise("a") == 1

    def test_get_or_raise_missing(self, registry: Registry[str, int]) -> None:
        with pytest.raises(KeyError, match="missing"):
            registry.get_or_raise("missing")

    def test_len(self, registry: Registry[str, int]) -> None:
        assert len(registry) == 0
        registry.register_sync("a", 1)
        assert len(registry) == 1

    def test_contains(self, registry: Registry[str, int]) -> None:
        registry.register_sync("a", 1)
        assert "a" in registry
        assert "b" not in registry

    def test_keys_and_values(self, registry: Registry[str, int]) -> None:
        registry.register_sync("a", 1)
        registry.register_sync("b", 2)
        assert set(registry.keys()) == {"a", "b"}
        assert set(registry.values()) == {1, 2}

    def test_list(self, registry: Registry[str, int]) -> None:
        registry.register_sync("a", 1)
        assert registry.list() == [("a", 1)]

    @pytest.mark.asyncio
    async def test_async_register(self) -> None:
        reg: Registry[str, int] = Registry()
        await reg.register("x", 10)
        assert reg.get("x") == 10

    @pytest.mark.asyncio
    async def test_async_clear(self) -> None:
        reg: Registry[str, int] = Registry()
        reg.register_sync("a", 1)
        await reg.clear()
        assert len(reg) == 0

    def test_overwrite(self, registry: Registry[str, int]) -> None:
        registry.register_sync("a", 1)
        registry.register_sync("a", 2)
        assert registry.get("a") == 2

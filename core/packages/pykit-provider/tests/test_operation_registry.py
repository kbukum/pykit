"""Tests for Registry and Binding."""

from __future__ import annotations

import pytest

from pykit_errors import AppError
from pykit_provider import Binding, Registry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class FakeProvider:
    """Minimal provider for testing."""

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name


# ---------------------------------------------------------------------------
# Binding
# ---------------------------------------------------------------------------


class TestBinding:
    def test_defaults(self) -> None:
        p = FakeProvider("p1")
        b = Binding(operation_id="op", provider=p)
        assert b.operation_id == "op"
        assert b.provider is p
        assert b.tiers == []
        assert b.priority == 0

    def test_custom_tiers_and_priority(self) -> None:
        p = FakeProvider("p2")
        b = Binding(operation_id="op", provider=p, tiers=["pro"], priority=5)
        assert b.tiers == ["pro"]
        assert b.priority == 5


# ---------------------------------------------------------------------------
# Registry — resolve
# ---------------------------------------------------------------------------


class TestRegistryResolve:
    def test_resolve_single_binding(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        p = FakeProvider("only")
        reg.bind(Binding(operation_id="transcribe", provider=p))
        assert reg.resolve("transcribe") is p

    def test_resolve_respects_priority(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        low = FakeProvider("low")
        high = FakeProvider("high")
        reg.bind(Binding(operation_id="op", provider=high, priority=10))
        reg.bind(Binding(operation_id="op", provider=low, priority=1))
        assert reg.resolve("op") is low

    def test_resolve_filters_by_tier(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        pro = FakeProvider("pro")
        free = FakeProvider("free")
        reg.bind(Binding(operation_id="op", provider=pro, tiers=["pro"]))
        reg.bind(Binding(operation_id="op", provider=free, tiers=["free"]))
        assert reg.resolve("op", tier="pro") is pro
        assert reg.resolve("op", tier="free") is free

    def test_resolve_empty_tiers_matches_all(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        p = FakeProvider("universal")
        reg.bind(Binding(operation_id="op", provider=p, tiers=[]))
        assert reg.resolve("op", tier="any-tier") is p
        assert reg.resolve("op", tier="") is p

    def test_resolve_tier_priority_combined(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        a = FakeProvider("a")
        b = FakeProvider("b")
        reg.bind(Binding(operation_id="op", provider=a, tiers=["pro"], priority=5))
        reg.bind(Binding(operation_id="op", provider=b, tiers=["pro"], priority=1))
        assert reg.resolve("op", tier="pro") is b

    def test_resolve_unknown_operation_raises(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        with pytest.raises(AppError) as exc_info:
            reg.resolve("nonexistent")
        assert exc_info.value.is_not_found

    def test_resolve_no_tier_match_raises(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        p = FakeProvider("restricted")
        reg.bind(Binding(operation_id="op", provider=p, tiers=["enterprise"]))
        with pytest.raises(AppError) as exc_info:
            reg.resolve("op", tier="free")
        assert exc_info.value.is_not_found


# ---------------------------------------------------------------------------
# Registry — list_bindings
# ---------------------------------------------------------------------------


class TestRegistryListBindings:
    def test_list_empty(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        assert reg.list_bindings("unknown") == []

    def test_list_returns_sorted_by_priority(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        p1 = FakeProvider("p1")
        p2 = FakeProvider("p2")
        p3 = FakeProvider("p3")
        reg.bind(Binding(operation_id="op", provider=p3, priority=10))
        reg.bind(Binding(operation_id="op", provider=p1, priority=1))
        reg.bind(Binding(operation_id="op", provider=p2, priority=5))
        bindings = reg.list_bindings("op")
        assert len(bindings) == 3
        assert bindings[0].provider is p1
        assert bindings[1].provider is p2
        assert bindings[2].provider is p3

    def test_list_does_not_affect_other_operations(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        reg.bind(Binding(operation_id="a", provider=FakeProvider("pa")))
        reg.bind(Binding(operation_id="b", provider=FakeProvider("pb")))
        assert len(reg.list_bindings("a")) == 1
        assert len(reg.list_bindings("b")) == 1


# ---------------------------------------------------------------------------
# Registry — bind
# ---------------------------------------------------------------------------


class TestRegistryBind:
    def test_bind_multiple_same_operation(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        for i in range(3):
            reg.bind(Binding(operation_id="op", provider=FakeProvider(f"p{i}")))
        assert len(reg.list_bindings("op")) == 3

    def test_bind_different_operations(self) -> None:
        reg: Registry[FakeProvider] = Registry()
        reg.bind(Binding(operation_id="a", provider=FakeProvider("pa")))
        reg.bind(Binding(operation_id="b", provider=FakeProvider("pb")))
        assert reg.resolve("a").name == "pa"
        assert reg.resolve("b").name == "pb"

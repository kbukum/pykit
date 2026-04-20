"""Tests for OperationRegistry and OperationBinding."""

from __future__ import annotations

import pytest

from pykit_errors import AppError
from pykit_provider import OperationBinding, OperationRegistry

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
# OperationBinding
# ---------------------------------------------------------------------------


class TestOperationBinding:
    def test_defaults(self) -> None:
        p = FakeProvider("p1")
        b = OperationBinding(operation_id="op", provider=p)
        assert b.operation_id == "op"
        assert b.provider is p
        assert b.tiers == []
        assert b.priority == 0

    def test_custom_tiers_and_priority(self) -> None:
        p = FakeProvider("p2")
        b = OperationBinding(operation_id="op", provider=p, tiers=["pro"], priority=5)
        assert b.tiers == ["pro"]
        assert b.priority == 5


# ---------------------------------------------------------------------------
# OperationRegistry — resolve
# ---------------------------------------------------------------------------


class TestOperationRegistryResolve:
    def test_resolve_single_binding(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        p = FakeProvider("only")
        reg.bind(OperationBinding(operation_id="transcribe", provider=p))
        assert reg.resolve("transcribe") is p

    def test_resolve_respects_priority(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        low = FakeProvider("low")
        high = FakeProvider("high")
        reg.bind(OperationBinding(operation_id="op", provider=high, priority=10))
        reg.bind(OperationBinding(operation_id="op", provider=low, priority=1))
        assert reg.resolve("op") is low

    def test_resolve_filters_by_tier(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        pro = FakeProvider("pro")
        free = FakeProvider("free")
        reg.bind(OperationBinding(operation_id="op", provider=pro, tiers=["pro"]))
        reg.bind(OperationBinding(operation_id="op", provider=free, tiers=["free"]))
        assert reg.resolve("op", tier="pro") is pro
        assert reg.resolve("op", tier="free") is free

    def test_resolve_empty_tiers_matches_all(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        p = FakeProvider("universal")
        reg.bind(OperationBinding(operation_id="op", provider=p, tiers=[]))
        assert reg.resolve("op", tier="any-tier") is p
        assert reg.resolve("op", tier="") is p

    def test_resolve_tier_priority_combined(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        a = FakeProvider("a")
        b = FakeProvider("b")
        reg.bind(OperationBinding(operation_id="op", provider=a, tiers=["pro"], priority=5))
        reg.bind(OperationBinding(operation_id="op", provider=b, tiers=["pro"], priority=1))
        assert reg.resolve("op", tier="pro") is b

    def test_resolve_unknown_operation_raises(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        with pytest.raises(AppError) as exc_info:
            reg.resolve("nonexistent")
        assert exc_info.value.is_not_found

    def test_resolve_no_tier_match_raises(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        p = FakeProvider("restricted")
        reg.bind(OperationBinding(operation_id="op", provider=p, tiers=["enterprise"]))
        with pytest.raises(AppError) as exc_info:
            reg.resolve("op", tier="free")
        assert exc_info.value.is_not_found


# ---------------------------------------------------------------------------
# OperationRegistry — list_bindings
# ---------------------------------------------------------------------------


class TestOperationRegistryListBindings:
    def test_list_empty(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        assert reg.list_bindings("unknown") == []

    def test_list_returns_sorted_by_priority(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        p1 = FakeProvider("p1")
        p2 = FakeProvider("p2")
        p3 = FakeProvider("p3")
        reg.bind(OperationBinding(operation_id="op", provider=p3, priority=10))
        reg.bind(OperationBinding(operation_id="op", provider=p1, priority=1))
        reg.bind(OperationBinding(operation_id="op", provider=p2, priority=5))
        bindings = reg.list_bindings("op")
        assert len(bindings) == 3
        assert bindings[0].provider is p1
        assert bindings[1].provider is p2
        assert bindings[2].provider is p3

    def test_list_does_not_affect_other_operations(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        reg.bind(OperationBinding(operation_id="a", provider=FakeProvider("pa")))
        reg.bind(OperationBinding(operation_id="b", provider=FakeProvider("pb")))
        assert len(reg.list_bindings("a")) == 1
        assert len(reg.list_bindings("b")) == 1


# ---------------------------------------------------------------------------
# OperationRegistry — bind
# ---------------------------------------------------------------------------


class TestOperationRegistryBind:
    def test_bind_multiple_same_operation(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        for i in range(3):
            reg.bind(OperationBinding(operation_id="op", provider=FakeProvider(f"p{i}")))
        assert len(reg.list_bindings("op")) == 3

    def test_bind_different_operations(self) -> None:
        reg: OperationRegistry[FakeProvider] = OperationRegistry()
        reg.bind(OperationBinding(operation_id="a", provider=FakeProvider("pa")))
        reg.bind(OperationBinding(operation_id="b", provider=FakeProvider("pb")))
        assert reg.resolve("a").name == "pa"
        assert reg.resolve("b").name == "pb"

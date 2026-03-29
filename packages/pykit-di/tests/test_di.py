"""Tests for pykit_di."""

from __future__ import annotations

import pytest

from pykit_di import Container, RegistrationMode
from pykit_di.container import CircularDependencyError

# ---------------------------------------------------------------------------
# Eager registration
# ---------------------------------------------------------------------------


class TestEagerRegistration:
    def test_factory_runs_immediately(self) -> None:
        c = Container()
        called = False

        def factory() -> str:
            nonlocal called
            called = True
            return "eager-value"

        c.register("svc", factory, RegistrationMode.EAGER)
        assert called

    def test_resolve_returns_value(self) -> None:
        c = Container()
        c.register("svc", lambda: "hello", RegistrationMode.EAGER)
        assert c.resolve("svc") == "hello"

    def test_resolve_returns_same_instance(self) -> None:
        c = Container()
        obj = object()
        c.register("svc", lambda: obj, RegistrationMode.EAGER)
        assert c.resolve("svc") is obj
        assert c.resolve("svc") is obj


# ---------------------------------------------------------------------------
# Lazy registration
# ---------------------------------------------------------------------------


class TestLazyRegistration:
    def test_factory_deferred(self) -> None:
        c = Container()
        call_count = 0

        def factory() -> str:
            nonlocal call_count
            call_count += 1
            return "lazy-value"

        c.register_lazy("svc", factory)
        assert call_count == 0

    def test_factory_runs_on_first_resolve(self) -> None:
        c = Container()
        call_count = 0

        def factory() -> str:
            nonlocal call_count
            call_count += 1
            return "lazy-value"

        c.register_lazy("svc", factory)
        assert c.resolve("svc") == "lazy-value"
        assert call_count == 1

    def test_result_cached(self) -> None:
        c = Container()
        call_count = 0

        def factory() -> str:
            nonlocal call_count
            call_count += 1
            return "cached"

        c.register_lazy("svc", factory)
        c.resolve("svc")
        c.resolve("svc")
        assert call_count == 1

    def test_register_with_mode_lazy(self) -> None:
        c = Container()
        c.register("x", lambda: 42, RegistrationMode.LAZY)
        assert c.resolve("x") == 42


# ---------------------------------------------------------------------------
# Singleton registration
# ---------------------------------------------------------------------------


class TestSingletonRegistration:
    def test_singleton_deferred_and_cached(self) -> None:
        c = Container()
        call_count = 0

        def factory() -> str:
            nonlocal call_count
            call_count += 1
            return "singleton"

        c.register_singleton("svc", factory)
        assert call_count == 0
        assert c.resolve("svc") == "singleton"
        assert call_count == 1
        c.resolve("svc")
        assert call_count == 1

    def test_register_with_mode_singleton(self) -> None:
        c = Container()
        c.register("x", lambda: 99, RegistrationMode.SINGLETON)
        assert c.resolve("x") == 99


# ---------------------------------------------------------------------------
# register_instance
# ---------------------------------------------------------------------------


class TestRegisterInstance:
    def test_resolve_returns_exact_instance(self) -> None:
        c = Container()
        obj = {"key": "value"}
        c.register_instance("cfg", obj)
        assert c.resolve("cfg") is obj

    def test_no_factory_needed(self) -> None:
        c = Container()
        c.register_instance("val", 42)
        assert c.resolve("val") == 42


# ---------------------------------------------------------------------------
# Type checking on resolve
# ---------------------------------------------------------------------------


class TestResolveTypeChecking:
    def test_matching_type(self) -> None:
        c = Container()
        c.register_instance("num", 42)
        assert c.resolve("num", int) == 42

    def test_mismatched_type_raises(self) -> None:
        c = Container()
        c.register_instance("num", 42)
        with pytest.raises(TypeError, match="expected str"):
            c.resolve("num", str)

    def test_subclass_passes(self) -> None:
        c = Container()
        c.register_instance("flag", True)
        assert c.resolve("flag", int) is True  # bool is subclass of int


# ---------------------------------------------------------------------------
# resolve_all
# ---------------------------------------------------------------------------


class TestResolveAll:
    def test_returns_all(self) -> None:
        c = Container()
        c.register_instance("a", 1)
        c.register_instance("b", "two")
        c.register_instance("c", 3)
        assert set(c.resolve_all()) == {1, "two", 3}

    def test_filtered_by_type(self) -> None:
        c = Container()
        c.register_instance("a", 1)
        c.register_instance("b", "two")
        c.register_instance("c", 3)
        result = c.resolve_all(int)
        assert set(result) == {1, 3} or set(result) == {1, 3}
        assert all(isinstance(v, int) for v in result)

    def test_empty_container(self) -> None:
        c = Container()
        assert c.resolve_all() == []


# ---------------------------------------------------------------------------
# has / names
# ---------------------------------------------------------------------------


class TestIntrospection:
    def test_has(self) -> None:
        c = Container()
        assert not c.has("x")
        c.register_instance("x", 1)
        assert c.has("x")

    def test_names(self) -> None:
        c = Container()
        c.register_instance("b", 2)
        c.register_instance("a", 1)
        assert set(c.names()) == {"a", "b"}

    def test_names_empty(self) -> None:
        c = Container()
        assert c.names() == []


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_removes_all(self) -> None:
        c = Container()
        c.register_instance("a", 1)
        c.register_lazy("b", lambda: 2)
        c.clear()
        assert c.names() == []
        assert not c.has("a")

    def test_resolve_after_clear_raises(self) -> None:
        c = Container()
        c.register_instance("x", 1)
        c.clear()
        with pytest.raises(KeyError):
            c.resolve("x")


# ---------------------------------------------------------------------------
# Circular dependency detection
# ---------------------------------------------------------------------------


class TestCircularDependency:
    def test_self_referencing_factory(self) -> None:
        c = Container()
        c.register_lazy("loop", lambda: c.resolve("loop"))
        with pytest.raises(CircularDependencyError, match="loop"):
            c.resolve("loop")

    def test_indirect_cycle(self) -> None:
        c = Container()
        c.register_lazy("a", lambda: c.resolve("b"))
        c.register_lazy("b", lambda: c.resolve("a"))
        with pytest.raises(CircularDependencyError):
            c.resolve("a")


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


class TestErrors:
    def test_resolve_unregistered(self) -> None:
        c = Container()
        with pytest.raises(KeyError, match="not registered"):
            c.resolve("missing")

    def test_factory_exception_propagates(self) -> None:
        c = Container()
        c.register_lazy("bad", lambda: 1 / 0)
        with pytest.raises(ZeroDivisionError):
            c.resolve("bad")

    def test_eager_factory_exception_propagates(self) -> None:
        with pytest.raises(ZeroDivisionError):
            c = Container()
            c.register("bad", lambda: 1 / 0, RegistrationMode.EAGER)


# ---------------------------------------------------------------------------
# Overwrite registration
# ---------------------------------------------------------------------------


class TestOverwrite:
    def test_re_register_replaces(self) -> None:
        c = Container()
        c.register_instance("x", 1)
        c.register_instance("x", 2)
        assert c.resolve("x") == 2


# ---------------------------------------------------------------------------
# RegistrationMode enum values
# ---------------------------------------------------------------------------


class TestRegistrationMode:
    def test_values(self) -> None:
        assert RegistrationMode.EAGER == "eager"
        assert RegistrationMode.LAZY == "lazy"
        assert RegistrationMode.SINGLETON == "singleton"

    def test_is_str(self) -> None:
        assert isinstance(RegistrationMode.EAGER, str)

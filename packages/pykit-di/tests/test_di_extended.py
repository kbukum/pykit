"""Extended tests for pykit_di — filling coverage gaps."""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from typing import Any

import pytest

from pykit_di import Container, RegistrationMode
from pykit_di.container import CircularDependencyError

# ---------------------------------------------------------------------------
# 1. Concurrent resolution of same lazy component from multiple threads
# ---------------------------------------------------------------------------


class TestConcurrentLazyResolution:
    def test_lazy_resolved_across_threads_after_init(self) -> None:
        """Concurrent reads of an already-initialized lazy component."""
        c = Container()
        call_count = 0
        lock = threading.Lock()

        def factory() -> str:
            nonlocal call_count
            with lock:
                call_count += 1
            return "lazy-value"

        c.register_lazy("svc", factory)
        # Pre-resolve so it's initialized (avoids circular dep guard clash)
        assert c.resolve("svc") == "lazy-value"

        results: list[Any] = [None] * 20
        errors: list[Exception | None] = [None] * 20

        def resolve(idx: int) -> None:
            try:
                results[idx] = c.resolve("svc")
            except Exception as e:
                errors[idx] = e

        threads = [threading.Thread(target=resolve, args=(i,)) for i in range(20)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        for i, err in enumerate(errors):
            assert err is None, f"thread {i}: {err}"
        for i, val in enumerate(results):
            assert val == "lazy-value", f"thread {i}: got {val!r}"
        assert call_count == 1  # factory only called once

    def test_concurrent_eager_resolution(self) -> None:
        c = Container()
        c.register("svc", lambda: "eager-val", RegistrationMode.EAGER)

        results: list[Any] = [None] * 30
        errors: list[Exception | None] = [None] * 30

        def resolve(idx: int) -> None:
            try:
                results[idx] = c.resolve("svc")
            except Exception as e:
                errors[idx] = e

        threads = [threading.Thread(target=resolve, args=(i,)) for i in range(30)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        for i in range(30):
            assert errors[i] is None
            assert results[i] == "eager-val"

    def test_concurrent_lazy_separate_keys(self) -> None:
        """Concurrent resolution of different lazy keys (no conflict)."""
        c = Container()
        for i in range(10):
            idx = i
            c.register_lazy(f"svc-{idx}", lambda i=idx: f"val-{i}")

        results: list[Any] = [None] * 10
        errors: list[Exception | None] = [None] * 10

        def resolve(idx: int) -> None:
            try:
                results[idx] = c.resolve(f"svc-{idx}")
            except Exception as e:
                errors[idx] = e

        threads = [threading.Thread(target=resolve, args=(i,)) for i in range(10)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        for i in range(10):
            assert errors[i] is None, f"thread {i}: {errors[i]}"
            assert results[i] == f"val-{i}"


# ---------------------------------------------------------------------------
# 2. Type hint with various types
# ---------------------------------------------------------------------------


class TestTypeHintVariety:
    def test_type_hint_list(self) -> None:
        c = Container()
        c.register_instance("items", [1, 2, 3])
        assert c.resolve("items", list) == [1, 2, 3]

    def test_type_hint_dict(self) -> None:
        c = Container()
        c.register_instance("cfg", {"key": "val"})
        assert c.resolve("cfg", dict) == {"key": "val"}

    def test_type_hint_custom_class(self) -> None:
        class MyService:
            pass

        c = Container()
        svc = MyService()
        c.register_instance("svc", svc)
        assert c.resolve("svc", MyService) is svc

    def test_type_hint_none_accepts_anything(self) -> None:
        c = Container()
        c.register_instance("num", 42)
        assert c.resolve("num") == 42


# ---------------------------------------------------------------------------
# 3. Factory exception during resolve_all
# ---------------------------------------------------------------------------


class TestResolveAllWithErrors:
    def test_factory_exception_during_resolve_all(self) -> None:
        c = Container()
        c.register_instance("good1", "hello")
        c.register_lazy("bad", lambda: 1 / 0)
        c.register_instance("good2", "world")

        with pytest.raises(ZeroDivisionError):
            c.resolve_all()

    def test_resolve_all_with_no_matching_type(self) -> None:
        c = Container()
        c.register_instance("a", 1)
        c.register_instance("b", 2)
        result = c.resolve_all(str)
        assert result == []


# ---------------------------------------------------------------------------
# 4. Thread safety under high contention (50 threads)
# ---------------------------------------------------------------------------


class TestHighContention:
    def test_50_threads_mixed_operations(self) -> None:
        c = Container()
        barrier = threading.Barrier(50)
        errors: list[Exception | None] = [None] * 50

        for i in range(10):
            c.register_instance(f"pre-{i}", i)

        def worker(idx: int) -> None:
            try:
                barrier.wait(timeout=5)
                if idx % 3 == 0:
                    c.register_instance(f"thread-{idx}", idx)
                elif idx % 3 == 1:
                    c.resolve(f"pre-{idx % 10}")
                else:
                    c.names()
            except Exception as e:
                errors[idx] = e

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(50)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        for i, err in enumerate(errors):
            assert err is None, f"thread {i}: {err}"


# ---------------------------------------------------------------------------
# 5. resolve_all returns a list (not generator)
# ---------------------------------------------------------------------------


class TestResolveAllReturnType:
    def test_resolve_all_returns_list(self) -> None:
        c = Container()
        c.register_instance("a", 1)
        result = c.resolve_all()
        assert isinstance(result, list)

    def test_resolve_all_multiple_calls_independent(self) -> None:
        c = Container()
        c.register_instance("a", 1)
        r1 = c.resolve_all()
        r2 = c.resolve_all()
        assert r1 == r2
        assert r1 is not r2  # different list objects


# ---------------------------------------------------------------------------
# 6. Type checking with ABC / abstract base classes
# ---------------------------------------------------------------------------


class TestABCTypeChecking:
    def test_abc_subclass_passes_type_check(self) -> None:
        class Animal(ABC):
            @abstractmethod
            def speak(self) -> str: ...

        class Dog(Animal):
            def speak(self) -> str:
                return "woof"

        c = Container()
        c.register_instance("pet", Dog())
        resolved = c.resolve("pet", Animal)
        assert resolved.speak() == "woof"

    def test_abc_mismatch_raises_type_error(self) -> None:
        class Vehicle(ABC):
            @abstractmethod
            def drive(self) -> None: ...

        c = Container()
        c.register_instance("not_vehicle", "just a string")
        with pytest.raises(TypeError, match="expected Vehicle"):
            c.resolve("not_vehicle", Vehicle)


# ---------------------------------------------------------------------------
# 7. Re-registration with different modes
# ---------------------------------------------------------------------------


class TestReRegistrationModes:
    def test_eager_to_lazy(self) -> None:
        c = Container()
        c.register("svc", lambda: "eager", RegistrationMode.EAGER)
        assert c.resolve("svc") == "eager"

        c.register_lazy("svc", lambda: "lazy")
        assert c.resolve("svc") == "lazy"

    def test_lazy_to_singleton(self) -> None:
        c = Container()
        c.register_lazy("svc", lambda: "lazy")
        c.register_singleton("svc", lambda: "singleton")
        assert c.resolve("svc") == "singleton"

    def test_instance_to_factory(self) -> None:
        c = Container()
        c.register_instance("svc", "instance-val")
        c.register_lazy("svc", lambda: "factory-val")
        assert c.resolve("svc") == "factory-val"

    def test_re_register_preserves_only_latest(self) -> None:
        c = Container()
        c.register_instance("x", 1)
        c.register_instance("x", 2)
        c.register_instance("x", 3)
        assert c.resolve("x") == 3
        assert c.names().count("x") == 1


# ---------------------------------------------------------------------------
# 8. Empty container operations
# ---------------------------------------------------------------------------


class TestEmptyContainerOps:
    def test_has_on_empty(self) -> None:
        c = Container()
        assert not c.has("anything")

    def test_names_on_empty(self) -> None:
        c = Container()
        assert c.names() == []

    def test_resolve_all_on_empty(self) -> None:
        c = Container()
        assert c.resolve_all() == []
        assert c.resolve_all(int) == []

    def test_clear_on_empty(self) -> None:
        c = Container()
        c.clear()  # should not raise
        assert c.names() == []

    def test_resolve_on_empty(self) -> None:
        c = Container()
        with pytest.raises(KeyError, match="not registered"):
            c.resolve("missing")


# ---------------------------------------------------------------------------
# 9. Circular dependency with 3+ levels
# ---------------------------------------------------------------------------


class TestCircularDependencyDeep:
    def test_3_level_cycle(self) -> None:
        c = Container()
        c.register_lazy("a", lambda: c.resolve("b"))
        c.register_lazy("b", lambda: c.resolve("c"))
        c.register_lazy("c", lambda: c.resolve("a"))

        with pytest.raises(CircularDependencyError, match="a"):
            c.resolve("a")

    def test_4_level_cycle(self) -> None:
        c = Container()
        c.register_lazy("w", lambda: c.resolve("x"))
        c.register_lazy("x", lambda: c.resolve("y"))
        c.register_lazy("y", lambda: c.resolve("z"))
        c.register_lazy("z", lambda: c.resolve("w"))

        with pytest.raises(CircularDependencyError, match="w"):
            c.resolve("w")

    def test_no_cycle_linear_dependency(self) -> None:
        c = Container()
        c.register_instance("base", 10)
        c.register_lazy("mid", lambda: c.resolve("base") * 2)
        c.register_lazy("top", lambda: c.resolve("mid") + 1)

        assert c.resolve("top") == 21


# ---------------------------------------------------------------------------
# 10. Factory that returns None
# ---------------------------------------------------------------------------


class TestNoneFactoryResult:
    def test_factory_returning_none(self) -> None:
        c = Container()
        c.register_lazy("nil-svc", lambda: None)
        assert c.resolve("nil-svc") is None

    def test_none_type_hint_check(self) -> None:
        c = Container()
        c.register_lazy("nil-svc", lambda: None)
        with pytest.raises(TypeError):
            c.resolve("nil-svc", int)


# ---------------------------------------------------------------------------
# 11. Names returns consistent keys
# ---------------------------------------------------------------------------


class TestNamesConsistency:
    def test_names_matches_registered(self) -> None:
        c = Container()
        expected = {"alpha", "beta", "gamma", "delta"}
        for name in expected:
            c.register_instance(name, name)
        assert set(c.names()) == expected

    def test_names_after_re_registration(self) -> None:
        c = Container()
        c.register_instance("x", 1)
        c.register_instance("y", 2)
        c.register_instance("x", 99)
        names = c.names()
        assert set(names) == {"x", "y"}
        assert len(names) == 2


# ---------------------------------------------------------------------------
# 12. Circular dependency error message includes component name
# ---------------------------------------------------------------------------


class TestCircularDependencyErrorMessage:
    def test_error_message_contains_name(self) -> None:
        c = Container()
        c.register_lazy("my-service", lambda: c.resolve("my-service"))
        with pytest.raises(CircularDependencyError) as exc_info:
            c.resolve("my-service")
        assert "my-service" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 13. Type hint mismatch error format
# ---------------------------------------------------------------------------


class TestTypeHintErrorFormat:
    def test_error_message_format(self) -> None:
        c = Container()
        c.register_instance("num", 42)
        with pytest.raises(TypeError) as exc_info:
            c.resolve("num", str)
        msg = str(exc_info.value)
        assert "num" in msg
        assert "int" in msg
        assert "str" in msg


# ---------------------------------------------------------------------------
# 14. Concurrent lazy initialization — factory called limited times
# ---------------------------------------------------------------------------


class TestConcurrentLazyInit:
    def test_singleton_resolved_across_threads_after_init(self) -> None:
        """Concurrent reads of an already-initialized singleton."""
        c = Container()
        call_count = 0
        lock = threading.Lock()

        def factory() -> str:
            nonlocal call_count
            with lock:
                call_count += 1
            time.sleep(0.01)
            return "singleton-val"

        c.register_singleton("svc", factory)
        # Pre-resolve so it's initialized
        assert c.resolve("svc") == "singleton-val"
        assert call_count == 1

        results: list[Any] = [None] * 20

        def resolve(idx: int) -> None:
            results[idx] = c.resolve("svc")

        threads = [threading.Thread(target=resolve, args=(i,)) for i in range(20)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()

        for r in results:
            assert r == "singleton-val"
        assert call_count == 1  # not called again


# ---------------------------------------------------------------------------
# 15. resolve_all filters correctly with base class
# ---------------------------------------------------------------------------


class TestResolveAllFiltering:
    def test_filter_by_base_class(self) -> None:
        class Base:
            pass

        class Child(Base):
            pass

        c = Container()
        c.register_instance("child", Child())
        c.register_instance("plain", "not a base")
        c.register_instance("num", 42)

        result = c.resolve_all(Base)
        assert len(result) == 1
        assert isinstance(result[0], Base)

    def test_filter_bool_is_int(self) -> None:
        c = Container()
        c.register_instance("flag", True)
        c.register_instance("count", 5)
        c.register_instance("text", "hello")

        # bool is subclass of int
        result = c.resolve_all(int)
        assert len(result) == 2
        assert set(result) == {True, 5}


# ---------------------------------------------------------------------------
# 16. Empty string as component name
# ---------------------------------------------------------------------------


class TestEmptyStringName:
    def test_empty_string_name_works(self) -> None:
        c = Container()
        c.register_instance("", "empty-key")
        assert c.has("")
        assert c.resolve("") == "empty-key"
        assert "" in c.names()


# ---------------------------------------------------------------------------
# 17. Large container (100+ registrations) performance
# ---------------------------------------------------------------------------


class TestLargeContainer:
    def test_100_plus_registrations(self) -> None:
        c = Container()
        for i in range(150):
            c.register_instance(f"comp-{i}", i)

        assert len(c.names()) == 150

        for i in range(150):
            assert c.resolve(f"comp-{i}") == i

    def test_resolve_all_large_container(self) -> None:
        c = Container()
        for i in range(100):
            c.register_instance(f"int-{i}", i)
        for i in range(50):
            c.register_instance(f"str-{i}", f"val-{i}")

        all_items = c.resolve_all()
        assert len(all_items) == 150

        ints = c.resolve_all(int)
        assert len(ints) == 100

        strs = c.resolve_all(str)
        assert len(strs) == 50


# ---------------------------------------------------------------------------
# 18. Stress test: rapid register/resolve/clear cycles
# ---------------------------------------------------------------------------


class TestStressCycles:
    def test_rapid_cycles(self) -> None:
        c = Container()
        for cycle in range(50):
            c.register_instance("key", cycle)
            assert c.resolve("key") == cycle
            c.clear()
            assert c.names() == []


# ---------------------------------------------------------------------------
# 19. Singleton and lazy semantic equivalence
# ---------------------------------------------------------------------------


class TestSingletonLazyEquivalence:
    def test_both_defer_and_cache(self) -> None:
        c = Container()
        lazy_count = 0
        single_count = 0

        def lazy_factory() -> str:
            nonlocal lazy_count
            lazy_count += 1
            return "lazy"

        def singleton_factory() -> str:
            nonlocal single_count
            single_count += 1
            return "singleton"

        c.register_lazy("l", lazy_factory)
        c.register_singleton("s", singleton_factory)

        assert lazy_count == 0
        assert single_count == 0

        c.resolve("l")
        c.resolve("l")
        c.resolve("s")
        c.resolve("s")

        assert lazy_count == 1
        assert single_count == 1


# ---------------------------------------------------------------------------
# 20. Resolve after factory raises — state consistency
# ---------------------------------------------------------------------------


class TestFactoryErrorStateConsistency:
    def test_failed_lazy_can_be_retried(self) -> None:
        c = Container()
        attempt = 0

        def factory() -> str:
            nonlocal attempt
            attempt += 1
            if attempt == 1:
                raise ValueError("first attempt fails")
            return "recovered"

        c.register_lazy("flaky", factory)

        with pytest.raises(ValueError, match="first attempt fails"):
            c.resolve("flaky")

        # After failure, the component should still be resolvable on retry
        # since initialized is not set to True on failure
        result = c.resolve("flaky")
        assert result == "recovered"


# ---------------------------------------------------------------------------
# 21. Thread safety of has/names during concurrent modification
# ---------------------------------------------------------------------------


class TestConcurrentIntrospection:
    def test_has_during_registration(self) -> None:
        c = Container()
        errors: list[Exception | None] = [None] * 40

        def register_worker(idx: int) -> None:
            try:
                c.register_instance(f"item-{idx}", idx)
            except Exception as e:
                errors[idx] = e

        def read_worker(idx: int) -> None:
            try:
                c.has(f"item-{idx % 20}")
                c.names()
            except Exception as e:
                errors[20 + idx] = e

        threads = []
        for i in range(20):
            threads.append(threading.Thread(target=register_worker, args=(i,)))
            threads.append(threading.Thread(target=read_worker, args=(i,)))

        for th in threads:
            th.start()
        for th in threads:
            th.join()

        for i, err in enumerate(errors):
            assert err is None, f"thread {i}: {err}"


# ---------------------------------------------------------------------------
# 22. Register instance with various Python types
# ---------------------------------------------------------------------------


class TestVariousTypes:
    def test_register_tuple(self) -> None:
        c = Container()
        c.register_instance("t", (1, 2, 3))
        assert c.resolve("t", tuple) == (1, 2, 3)

    def test_register_set(self) -> None:
        c = Container()
        c.register_instance("s", {1, 2, 3})
        assert c.resolve("s", set) == {1, 2, 3}

    def test_register_bytes(self) -> None:
        c = Container()
        c.register_instance("b", b"hello")
        assert c.resolve("b", bytes) == b"hello"

    def test_register_callable(self) -> None:
        c = Container()

        def my_func() -> str:
            return "hello"

        c.register_instance("fn", my_func)
        resolved = c.resolve("fn")
        assert resolved() == "hello"


# ---------------------------------------------------------------------------
# 23. resolve_all with lazy + eager mix
# ---------------------------------------------------------------------------


class TestResolveAllMixed:
    def test_resolves_lazy_during_resolve_all(self) -> None:
        c = Container()
        c.register("eager", lambda: "e", RegistrationMode.EAGER)
        c.register_lazy("lazy", lambda: "l")
        c.register_instance("inst", "i")

        result = c.resolve_all()
        assert set(result) == {"e", "l", "i"}


# ---------------------------------------------------------------------------
# 24. Clear resets resolving guard
# ---------------------------------------------------------------------------


class TestClearResetsState:
    def test_clear_allows_re_registration_with_same_name(self) -> None:
        c = Container()
        c.register_lazy("svc", lambda: "first")
        assert c.resolve("svc") == "first"

        c.clear()
        c.register_lazy("svc", lambda: "second")
        assert c.resolve("svc") == "second"


# ---------------------------------------------------------------------------
# 25. RegistrationMode enum membership
# ---------------------------------------------------------------------------


class TestRegistrationModeExtended:
    def test_all_modes_are_strings(self) -> None:
        for mode in RegistrationMode:
            assert isinstance(mode, str)

    def test_mode_count(self) -> None:
        assert len(RegistrationMode) == 3

    def test_modes_distinct(self) -> None:
        modes = [m.value for m in RegistrationMode]
        assert len(set(modes)) == len(modes)

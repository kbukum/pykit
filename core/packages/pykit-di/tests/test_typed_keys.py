"""Typed-key tests for the DI container."""

from __future__ import annotations

import pytest

from pykit_di import (
    Container,
    Key,
    RegistrationMode,
    must_resolve_key,
    provide,
    provide_singleton,
    provide_transient,
    resolve_key,
)
from pykit_di.container import CircularDependencyError


class TestTypedKeys:
    def test_typed_lazy_and_singleton_apis(self) -> None:
        container = Container()
        lazy_key = Key[str]("lazy")
        singleton_key = Key[int]("singleton")

        provide(container, lazy_key, lambda: "value")
        provide_singleton(container, singleton_key, 42)

        assert resolve_key(container, lazy_key) == "value"
        assert must_resolve_key(container, singleton_key) == 42

    def test_transient_returns_new_instance_each_time(self) -> None:
        container = Container()
        key = Key[list[str]]("transient")

        provide_transient(container, key, list)

        first = resolve_key(container, key)
        second = resolve_key(container, key)

        assert first == []
        assert second == []
        assert first is not second
        assert RegistrationMode.TRANSIENT == "transient"

    def test_typed_key_circular_detection(self) -> None:
        container = Container()
        first = Key[str]("first")
        second = Key[str]("second")

        provide(container, first, lambda: resolve_key(container, second))
        provide(container, second, lambda: resolve_key(container, first))

        with pytest.raises(CircularDependencyError, match="first"):
            resolve_key(container, first)

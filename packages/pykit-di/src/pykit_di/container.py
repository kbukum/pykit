"""Dependency injection container with eager, lazy, singleton, and transient modes."""

from __future__ import annotations

import enum
import threading
import warnings
from collections.abc import Callable
from contextvars import ContextVar
from typing import Generic, TypeVar, cast, overload

T = TypeVar("T")

_resolving_var: ContextVar[frozenset[str]] = ContextVar("_resolving", default=frozenset())


class RegistrationMode(enum.StrEnum):
    """How a component factory is invoked."""

    EAGER = "eager"
    LAZY = "lazy"
    SINGLETON = "singleton"
    TRANSIENT = "transient"


class Key(Generic[T]):
    """Typed registration key."""

    __slots__ = ("_name",)

    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        """Return the string name used by the container."""
        return self._name


class _Registration:
    """Internal record for a registered component."""

    __slots__ = ("factory", "initialized", "instance", "mode", "name")

    def __init__(self, name: str, factory: Callable[[], object] | None, mode: RegistrationMode) -> None:
        self.name = name
        self.factory = factory
        self.mode = mode
        self.instance: object | None = None
        self.initialized = False


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected during resolution."""


class Container:
    """Dependency injection container.

    Supports four registration modes:
    - **EAGER**: factory runs immediately at registration time.
    - **LAZY**: factory runs on first ``resolve()``, result cached.
    - **SINGLETON**: alias for LAZY (deferred, cached).
    - **TRANSIENT**: factory runs on every ``resolve()``, result not cached.
    """

    def __init__(self) -> None:
        self._registrations: dict[str, _Registration] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _get_resolving() -> frozenset[str]:
        return _resolving_var.get()

    @staticmethod
    def _enter_resolving(name: str) -> None:
        current = _resolving_var.get()
        _resolving_var.set(current | {name})

    @staticmethod
    def _exit_resolving(name: str) -> None:
        current = _resolving_var.get()
        _resolving_var.set(current - {name})

    def register(
        self,
        name: str,
        factory: Callable[[], object],
        mode: RegistrationMode = RegistrationMode.EAGER,
    ) -> None:
        """Register a factory under *name* with the given *mode*."""
        with self._lock:
            reg = _Registration(name, factory, mode)
            if mode == RegistrationMode.EAGER:
                reg.instance = factory()
                reg.initialized = True
            self._registrations[name] = reg

    def register_instance(self, name: str, instance: object) -> None:
        """Register a pre-built *instance* (singleton shorthand)."""
        with self._lock:
            reg = _Registration(name, None, RegistrationMode.SINGLETON)
            reg.instance = instance
            reg.initialized = True
            self._registrations[name] = reg

    def register_lazy(self, name: str, factory: Callable[[], object]) -> None:
        """Shorthand for ``register(name, factory, RegistrationMode.LAZY)``."""
        self.register(name, factory, RegistrationMode.LAZY)

    def register_singleton(self, name: str, factory: Callable[[], object]) -> None:
        """Shorthand for ``register(name, factory, RegistrationMode.SINGLETON)``."""
        self.register(name, factory, RegistrationMode.SINGLETON)

    def register_transient(self, name: str, factory: Callable[[], object]) -> None:
        """Shorthand for ``register(name, factory, RegistrationMode.TRANSIENT)``."""
        self.register(name, factory, RegistrationMode.TRANSIENT)

    @overload
    def resolve(self, name: str, type_hint: type[T]) -> T: ...

    @overload
    def resolve(self, name: str, type_hint: None = ...) -> object: ...

    def resolve(self, name: str, type_hint: type[T] | None = None) -> T | object:
        """Resolve a component by *name*."""
        if type_hint is None:
            warnings.warn(
                "resolve() without type_hint returns object and is deprecated. "
                "Pass an explicit type: container.resolve(name, MyService)",
                DeprecationWarning,
                stacklevel=2,
            )
        with self._lock:
            reg = self._registrations.get(name)
            if reg is None:
                raise KeyError(f"Component '{name}' is not registered")

            if reg.initialized:
                return self._check_type(name, reg.instance, type_hint)

            if name in self._get_resolving():
                raise CircularDependencyError(f"Circular dependency detected while resolving '{name}'")
            self._enter_resolving(name)

        try:
            assert reg.factory is not None
            instance = reg.factory()
        finally:
            self._exit_resolving(name)

        if reg.mode != RegistrationMode.TRANSIENT:
            with self._lock:
                reg.instance = instance
                reg.initialized = True

        return self._check_type(name, instance, type_hint)

    @overload
    def resolve_all(self, type_hint: type[T]) -> list[T]: ...

    @overload
    def resolve_all(self, type_hint: None = ...) -> list[object]: ...

    def resolve_all(self, type_hint: type[T] | None = None) -> list[T] | list[object]:
        """Resolve all registered components, optionally filtered by type."""
        results: list[object] = []
        with self._lock:
            names = list(self._registrations)

        for name in names:
            instance = self.resolve(name, object)
            if type_hint is None or isinstance(instance, type_hint):
                results.append(instance)
        return cast("list[T] | list[object]", results)

    def has(self, name: str) -> bool:
        """Return ``True`` if *name* is registered."""
        with self._lock:
            return name in self._registrations

    def names(self) -> list[str]:
        """Return all registered component names."""
        with self._lock:
            return list(self._registrations)

    def clear(self) -> None:
        """Remove all registrations and reset internal state."""
        with self._lock:
            self._registrations.clear()

    @staticmethod
    def _check_type(name: str, instance: object, type_hint: type[T] | None) -> T | object:
        if type_hint is not None and not isinstance(instance, type_hint):
            raise TypeError(f"Component '{name}' is {type(instance).__name__}, expected {type_hint.__name__}")
        return instance


def provide(container: Container, key: Key[T], factory: Callable[..., T]) -> None:
    """Register a typed lazy factory."""
    container.register_lazy(key.name, cast("Callable[[], object]", factory))


def provide_singleton(container: Container, key: Key[T], instance: T) -> None:
    """Register a typed singleton instance."""
    container.register_instance(key.name, instance)


def provide_transient(container: Container, key: Key[T], factory: Callable[..., T]) -> None:
    """Register a typed transient factory."""
    container.register(
        key.name,
        cast("Callable[[], object]", factory),
        RegistrationMode.TRANSIENT,
    )


def resolve_key(container: Container, key: Key[T]) -> T:
    """Resolve a typed key."""
    return cast("T", container.resolve(key.name, object))


def must_resolve_key(container: Container, key: Key[T]) -> T:
    """Resolve a typed key or raise the underlying container error."""
    return resolve_key(container, key)

"""Dependency injection container with eager, lazy, and singleton registration modes."""

from __future__ import annotations

import enum
import threading
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, TypeVar

T = TypeVar("T")

_resolving_var: ContextVar[frozenset[str]] = ContextVar("_resolving", default=frozenset())


class RegistrationMode(enum.StrEnum):
    """How a component factory is invoked."""

    EAGER = "eager"
    LAZY = "lazy"
    SINGLETON = "singleton"


class _Registration:
    """Internal record for a registered component."""

    __slots__ = ("factory", "initialized", "instance", "mode", "name")

    def __init__(self, name: str, factory: Callable[[], Any] | None, mode: RegistrationMode) -> None:
        self.name = name
        self.factory = factory
        self.mode = mode
        self.instance: Any = None
        self.initialized = False


class CircularDependencyError(Exception):
    """Raised when a circular dependency is detected during resolution."""


class Container:
    """Dependency injection container.

    Supports three registration modes:
    - **EAGER**: factory runs immediately at registration time.
    - **LAZY**: factory runs on first ``resolve()``, result cached.
    - **SINGLETON**: alias for LAZY (deferred, cached).

    Circular dependency detection prevents infinite recursion when
    a factory calls ``resolve()`` on the same container for a name
    that is currently being resolved.
    """

    def __init__(self) -> None:
        self._registrations: dict[str, _Registration] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # ContextVar-based cycle detection helpers
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(
        self,
        name: str,
        factory: Callable[[], Any],
        mode: RegistrationMode = RegistrationMode.EAGER,
    ) -> None:
        """Register a factory under *name* with the given *mode*."""
        with self._lock:
            reg = _Registration(name, factory, mode)
            if mode == RegistrationMode.EAGER:
                reg.instance = factory()
                reg.initialized = True
            self._registrations[name] = reg

    def register_instance(self, name: str, instance: Any) -> None:
        """Register a pre-built *instance* (singleton shorthand)."""
        with self._lock:
            reg = _Registration(name, None, RegistrationMode.SINGLETON)
            reg.instance = instance
            reg.initialized = True
            self._registrations[name] = reg

    def register_lazy(self, name: str, factory: Callable[[], Any]) -> None:
        """Shorthand for ``register(name, factory, RegistrationMode.LAZY)``."""
        self.register(name, factory, RegistrationMode.LAZY)

    def register_singleton(self, name: str, factory: Callable[[], Any]) -> None:
        """Shorthand for ``register(name, factory, RegistrationMode.SINGLETON)``."""
        self.register(name, factory, RegistrationMode.SINGLETON)

    # ------------------------------------------------------------------
    # Resolution
    # ------------------------------------------------------------------

    def resolve(self, name: str, type_hint: type[T] | None = None) -> T:  # type: ignore[type-var]
        """Resolve a component by *name*.

        If *type_hint* is provided the resolved value is checked with
        ``isinstance`` and a ``TypeError`` is raised on mismatch.

        Raises ``KeyError`` if *name* is not registered.
        Raises ``CircularDependencyError`` on re-entrant resolution.
        """
        with self._lock:
            reg = self._registrations.get(name)
            if reg is None:
                raise KeyError(f"Component '{name}' is not registered")

            if reg.initialized:
                return self._check_type(name, reg.instance, type_hint)

            # Circular dependency guard
            if name in self._get_resolving():
                raise CircularDependencyError(f"Circular dependency detected while resolving '{name}'")
            self._enter_resolving(name)

        # Factory call outside lock to avoid deadlock, but guard is set.
        try:
            assert reg.factory is not None
            instance = reg.factory()
        finally:
            self._exit_resolving(name)

        with self._lock:
            reg.instance = instance
            reg.initialized = True

        return self._check_type(name, instance, type_hint)

    def resolve_all(self, type_hint: type[T] | None = None) -> list[T]:  # type: ignore[type-var]
        """Resolve **all** registered components, optionally filtered by *type_hint*."""
        results: list[Any] = []
        with self._lock:
            names = list(self._registrations)

        for name in names:
            instance = self.resolve(name)
            if type_hint is None or isinstance(instance, type_hint):
                results.append(instance)
        return results

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def has(self, name: str) -> bool:
        """Return ``True`` if *name* is registered."""
        with self._lock:
            return name in self._registrations

    def names(self) -> list[str]:
        """Return all registered component names."""
        with self._lock:
            return list(self._registrations)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self) -> None:
        """Remove all registrations and reset internal state."""
        with self._lock:
            self._registrations.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check_type(name: str, instance: Any, type_hint: type[T] | None) -> T:  # type: ignore[type-var]
        if type_hint is not None and not isinstance(instance, type_hint):
            raise TypeError(f"Component '{name}' is {type(instance).__name__}, expected {type_hint.__name__}")
        return instance  # type: ignore[return-value]

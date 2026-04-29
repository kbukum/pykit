"""pykit_di — Dependency injection container with typed keys."""

from __future__ import annotations

from pykit_di.container import (
    Container,
    Key,
    RegistrationMode,
    must_resolve_key,
    provide,
    provide_singleton,
    provide_transient,
    resolve_key,
)

__all__ = [
    "Container",
    "Key",
    "RegistrationMode",
    "must_resolve_key",
    "provide",
    "provide_singleton",
    "provide_transient",
    "resolve_key",
]

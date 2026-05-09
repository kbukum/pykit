"""Inference adapter registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pykit_inference.types import Inference

ProviderFactory = Callable[[dict[str, Any]], Inference]


class Registry:
    """Explicit registry of model-serving adapter factories."""

    def __init__(self) -> None:
        self._factories: dict[str, ProviderFactory] = {}

    def register(self, kind: str, factory: ProviderFactory) -> None:
        """Register an adapter factory under a stable kind."""
        normalized = kind.strip()
        if not normalized:
            raise ValueError("inference adapter kind is required")
        if normalized in self._factories:
            raise ValueError(f"inference adapter {normalized!r} already registered")
        self._factories[normalized] = factory

    def build(self, kind: str, config: dict[str, Any]) -> Inference:
        """Build an adapter from a registered kind and plain configuration."""
        try:
            factory = self._factories[kind]
        except KeyError as exc:
            raise ValueError(f"unknown inference adapter {kind!r}") from exc
        return factory(dict(config))

    def kinds(self) -> list[str]:
        """Return registered adapter kinds in stable order."""
        return sorted(self._factories)

"""pykit_workload.config — Configuration and factory registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pykit_workload.manager import Manager

_factories: dict[str, Callable[..., Manager]] = {}


@dataclass
class WorkloadConfig:
    provider: str = "docker"
    enabled: bool = False
    default_labels: dict[str, str] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.provider:
            raise ValueError("workload: provider is required")


def register_factory(name: str, factory: Callable[..., Manager]) -> None:
    """Register a manager factory for a named provider."""
    _factories[name] = factory


def create_manager(cfg: WorkloadConfig, provider_cfg: Any = None) -> Manager:
    """Create a manager instance using the registered factory for the configured provider."""
    cfg.validate()
    factory = _factories.get(cfg.provider)
    if factory is None:
        raise ValueError(f"workload: unsupported provider {cfg.provider!r}")
    return factory(cfg, provider_cfg)

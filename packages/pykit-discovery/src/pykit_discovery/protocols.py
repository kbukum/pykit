"""Discovery and Registry protocols."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from pykit_discovery.types import ServiceInstance


@runtime_checkable
class Discovery(Protocol):
    """Protocol for discovering service instances by name."""

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        """Return the instances registered for the given service."""


@runtime_checkable
class Registry(Protocol):
    """Protocol for registering and deregistering service instances."""

    async def register(self, instance: ServiceInstance) -> None:
        """Register a service instance."""

    async def deregister(self, instance_id: str) -> None:
        """Remove a service instance from the registry."""


@runtime_checkable
class Watcher(Protocol):
    """Optional extension for continuous service monitoring.

    Implementations yield updated instance lists whenever service
    membership changes, enabling live reconnection without polling.
    """

    def watch(self, service_name: str) -> AsyncIterator[list[ServiceInstance]]:
        """Yield updated instance lists for the given service."""

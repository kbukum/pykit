"""Discovery and Registry protocols."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_discovery.types import ServiceInstance


@runtime_checkable
class Discovery(Protocol):
    """Protocol for discovering service instances by name."""

    async def discover(self, service_name: str) -> list[ServiceInstance]: ...


@runtime_checkable
class Registry(Protocol):
    """Protocol for registering and deregistering service instances."""

    async def register(self, instance: ServiceInstance) -> None: ...

    async def deregister(self, instance_id: str) -> None: ...

"""Discovery component — lifecycle wrapper for service discovery."""

from __future__ import annotations

from datetime import UTC, datetime

from pykit_component import Health, HealthStatus
from pykit_discovery.protocols import Discovery, Registry
from pykit_discovery.static import StaticProvider
from pykit_discovery.types import ServiceInstance


class DiscoveryComponent:
    """Component protocol wrapper for discovery and registry."""

    def __init__(
        self,
        provider: StaticProvider | None = None,
    ) -> None:
        self._provider: StaticProvider = provider or StaticProvider()
        self._started = False

    @property
    def name(self) -> str:
        return "discovery"

    @property
    def discovery(self) -> Discovery:
        return self._provider  # type: ignore[return-value]

    @property
    def registry(self) -> Registry:
        return self._provider  # type: ignore[return-value]

    async def start(self) -> None:
        self._started = True

    async def stop(self) -> None:
        self._started = False

    async def health(self) -> Health:
        if not self._started:
            return Health(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="not started",
                timestamp=datetime.now(UTC),
            )
        return Health(
            name=self.name,
            status=HealthStatus.HEALTHY,
            message="running",
            timestamp=datetime.now(UTC),
        )

    async def register(self, instance: ServiceInstance) -> None:
        await self._provider.register(instance)

    async def deregister(self, instance_id: str) -> None:
        await self._provider.deregister(instance_id)

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        return await self._provider.discover(service_name)

"""In-memory static provider for dev/test."""

from __future__ import annotations

from pykit_discovery.types import ServiceInstance


class StaticProvider:
    """In-memory discovery and registry for development and testing."""

    def __init__(self) -> None:
        self._services: dict[str, dict[str, ServiceInstance]] = {}

    async def register(self, instance: ServiceInstance) -> None:
        if instance.name not in self._services:
            self._services[instance.name] = {}
        self._services[instance.name][instance.id] = instance

    async def deregister(self, instance_id: str) -> None:
        for service_instances in self._services.values():
            service_instances.pop(instance_id, None)

    async def discover(self, service_name: str) -> list[ServiceInstance]:
        instances = self._services.get(service_name, {})
        return [i for i in instances.values() if i.healthy]

"""Storage component with lifecycle management."""

from __future__ import annotations

from pykit_component import Health, HealthStatus
from pykit_storage.base import Storage
from pykit_storage.config import StorageConfig
from pykit_storage.registry import StorageRegistry, default_storage_registry


class StorageComponent:
    """Lifecycle-managed storage component."""

    def __init__(
        self,
        config: StorageConfig | None = None,
        *,
        registry: StorageRegistry | None = None,
    ) -> None:
        self._config = config or StorageConfig()
        self._registry = registry or default_storage_registry()
        self._storage: Storage | None = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def storage(self) -> Storage | None:
        return self._storage

    async def start(self) -> None:
        """Construct the configured storage backend."""
        if not self._config.enabled:
            return
        self._storage = self._registry.create(self._config)

    async def stop(self) -> None:
        self._storage = None

    async def health(self) -> Health:
        if not self._config.enabled:
            return Health(name=self.name, status=HealthStatus.HEALTHY, message="storage disabled")
        if self._storage is None:
            return Health(name=self.name, status=HealthStatus.UNHEALTHY, message="storage not started")
        return Health(name=self.name, status=HealthStatus.HEALTHY)

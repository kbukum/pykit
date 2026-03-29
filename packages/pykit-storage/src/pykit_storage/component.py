"""Storage component with lifecycle management."""

from __future__ import annotations

from pykit_component import Health, HealthStatus
from pykit_storage.base import Storage
from pykit_storage.config import StorageConfig
from pykit_storage.local import LocalStorage


class StorageComponent:
    """Lifecycle-managed storage component."""

    def __init__(self, config: StorageConfig | None = None) -> None:
        self._config = config or StorageConfig()
        self._storage: Storage | None = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def storage(self) -> Storage | None:
        return self._storage

    async def start(self) -> None:
        if self._config.provider == "local":
            self._storage = LocalStorage(
                base_path=self._config.base_path,
                public_url=self._config.public_url,
            )
        elif self._config.provider == "s3":
            msg = "S3 provider requires the 's3' extra: pip install pykit-storage[s3]"
            raise NotImplementedError(msg)
        else:
            msg = f"Unknown storage provider: {self._config.provider}"
            raise ValueError(msg)

    async def stop(self) -> None:
        self._storage = None

    async def health(self) -> Health:
        if self._storage is None:
            return Health(name=self.name, status=HealthStatus.UNHEALTHY, message="storage not started")
        return Health(name=self.name, status=HealthStatus.HEALTHY)

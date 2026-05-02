"""cache component with lifecycle management."""

from __future__ import annotations

from pykit_component import Health, HealthStatus
from pykit_cache.client import CacheClient
from pykit_cache.config import CacheConfig


class CacheComponent:
    """Lifecycle-managed cache component implementing the Component protocol."""

    def __init__(self, config: CacheConfig) -> None:
        self._config = config
        self._client: CacheClient | None = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def client(self) -> CacheClient | None:
        return self._client

    async def start(self) -> None:
        """Create the client and verify connectivity with a PING."""
        if not self._config.enabled:
            return
        self._client = CacheClient(self._config)
        await self._client.ping()

    async def stop(self) -> None:
        """Close the underlying cache connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def health(self) -> Health:
        """Return current health status."""
        if self._client is None:
            return Health(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="cache not initialized",
            )
        try:
            await self._client.ping()
        except Exception as exc:
            return Health(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"ping failed: {exc}",
            )
        return Health(name=self.name, status=HealthStatus.HEALTHY)

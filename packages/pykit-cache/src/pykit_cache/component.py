"""Cache component with lifecycle management."""

from __future__ import annotations

from pykit_cache.client import CacheClient
from pykit_cache.config import CacheConfig
from pykit_cache.registry import CacheRegistry, default_cache_registry
from pykit_component import Health, HealthStatus


class CacheComponent:
    """Lifecycle-managed cache component implementing the Component protocol."""

    def __init__(self, config: CacheConfig | None = None, *, registry: CacheRegistry | None = None) -> None:
        self._config = config or CacheConfig()
        self._registry = registry or default_cache_registry()
        self._client: CacheClient | None = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def client(self) -> CacheClient | None:
        return self._client

    async def start(self) -> None:
        """Create the client and verify backend health."""
        if not self._config.enabled:
            return
        self._client = CacheClient(self._config, registry=self._registry)
        await self._client.ping()

    async def stop(self) -> None:
        """Close the underlying cache backend."""
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
            ok = await self._client.ping()
        except Exception as exc:
            return Health(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message=f"ping failed: {exc}",
            )
        if not ok:
            return Health(name=self.name, status=HealthStatus.UNHEALTHY, message="ping failed")
        return Health(name=self.name, status=HealthStatus.HEALTHY)

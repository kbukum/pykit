"""Redis component with lifecycle management."""

from __future__ import annotations

from pykit_component import Health, HealthStatus
from pykit_redis.client import RedisClient
from pykit_redis.config import RedisConfig


class RedisComponent:
    """Lifecycle-managed Redis component implementing the Component protocol."""

    def __init__(self, config: RedisConfig) -> None:
        self._config = config
        self._client: RedisClient | None = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def client(self) -> RedisClient | None:
        return self._client

    async def start(self) -> None:
        """Create the client and verify connectivity with a PING."""
        if not self._config.enabled:
            return
        self._client = RedisClient(self._config)
        await self._client.ping()

    async def stop(self) -> None:
        """Close the underlying Redis connection."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def health(self) -> Health:
        """Return current health status."""
        if self._client is None:
            return Health(
                name=self.name,
                status=HealthStatus.UNHEALTHY,
                message="redis not initialized",
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

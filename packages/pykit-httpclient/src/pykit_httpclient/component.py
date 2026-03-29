"""Lifecycle-managed HTTP client component."""

from __future__ import annotations

import httpx

from pykit_component import Health, HealthStatus
from pykit_httpclient.client import HttpClient
from pykit_httpclient.config import HttpConfig


class HttpComponent:
    """Wraps HttpClient with component lifecycle management."""

    def __init__(self, config: HttpConfig) -> None:
        self._config = config
        self._client: HttpClient | None = None

    @property
    def name(self) -> str:
        return self._config.name

    @property
    def client(self) -> HttpClient | None:
        return self._client

    async def start(self) -> None:
        """Create the HTTP client."""
        self._client = HttpClient(self._config)

    async def stop(self) -> None:
        """Close the HTTP client and release resources."""
        if self._client is not None:
            await self._client.close()
            self._client = None

    async def health(self) -> Health:
        """Check component health."""
        if self._client is None:
            return Health(name=self.name, status=HealthStatus.UNHEALTHY, message="client not started")

        if not self._config.base_url:
            return Health(name=self.name, status=HealthStatus.HEALTHY)

        try:
            resp = await self._client._client.request("HEAD", self._config.base_url)
            if resp.status_code < 500:
                return Health(name=self.name, status=HealthStatus.HEALTHY)
            return Health(
                name=self.name,
                status=HealthStatus.DEGRADED,
                message=f"HEAD returned {resp.status_code}",
            )
        except httpx.HTTPError as exc:
            return Health(name=self.name, status=HealthStatus.UNHEALTHY, message=str(exc))

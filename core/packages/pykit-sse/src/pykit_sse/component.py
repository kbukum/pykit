"""SSE component — lifecycle wrapper around :class:`SSEHub`."""

from __future__ import annotations

from pykit_component import Description, Health, HealthStatus
from pykit_sse.hub import SSEHub


class SSEComponent:
    """Lifecycle-managed SSE hub implementing the Component protocol."""

    def __init__(self, path: str = "/events") -> None:
        self._hub = SSEHub()
        self._path = path

    @property
    def name(self) -> str:
        return "sse"

    @property
    def hub(self) -> SSEHub:
        return self._hub

    async def start(self) -> None:
        """Start the SSE component (no-op; hub is always ready)."""

    async def stop(self) -> None:
        """Stop the SSE component, closing all clients."""
        await self._hub.shutdown()

    async def health(self) -> Health:
        return Health(
            name=self.name,
            status=HealthStatus.HEALTHY,
            message=f"{self._hub.client_count} clients connected",
        )

    def describe(self) -> Description:
        return Description(
            name="SSE Hub",
            type="sse",
            details=f"Path: {self._path}",
        )

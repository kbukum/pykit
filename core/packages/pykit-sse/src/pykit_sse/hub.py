"""SSE hub — manages clients, registration, broadcast, and shutdown."""

from __future__ import annotations

from collections.abc import Callable

from pykit_sse.client import SSEClient
from pykit_sse.event import SSEEvent


class SSEHub:
    """Central event router managing client subscriptions and broadcasting."""

    def __init__(self) -> None:
        self._clients: dict[str, SSEClient] = {}

    def register(self, client: SSEClient) -> None:
        """Register a client with the hub."""
        self._clients[client.client_id] = client

    def unregister(self, client_id: str) -> None:
        """Remove and close a client."""
        client = self._clients.pop(client_id, None)
        if client is not None:
            client.close()

    async def broadcast(
        self,
        event: SSEEvent,
        filter_fn: Callable[[SSEClient], bool] | None = None,
    ) -> None:
        """Send *event* to all clients, or only those accepted by *filter_fn*."""
        for client in list(self._clients.values()):
            if filter_fn is not None and not filter_fn(client):
                continue
            await client.send(event)

    async def send_to(self, client_id: str, event: SSEEvent) -> None:
        """Send *event* to a specific client by ID.

        Raises :class:`KeyError` if the client is not registered.
        """
        client = self._clients.get(client_id)
        if client is None:
            raise KeyError(f"client '{client_id}' not registered")
        await client.send(event)

    @property
    def client_count(self) -> int:
        """Number of currently registered clients."""
        return len(self._clients)

    def get_client(self, client_id: str) -> SSEClient | None:
        """Return a client by ID, or ``None``."""
        return self._clients.get(client_id)

    async def shutdown(self) -> None:
        """Close and remove all clients."""
        for client in self._clients.values():
            client.close()
        self._clients.clear()

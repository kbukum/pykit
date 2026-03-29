"""SSE client with async queue-based event delivery."""

from __future__ import annotations

import asyncio
from typing import Any

from pykit_sse.event import SSEEvent


class SSEClient:
    """A connected SSE client with a buffered event queue.

    Each client has an :class:`asyncio.Queue` for non-blocking event delivery.
    """

    def __init__(self, client_id: str, metadata: dict[str, Any] | None = None) -> None:
        self.client_id = client_id
        self.metadata: dict[str, Any] = metadata or {}
        self.queue: asyncio.Queue[SSEEvent] = asyncio.Queue()
        self._closed = False

    async def send(self, event: SSEEvent) -> None:
        """Put *event* onto the client queue."""
        if not self._closed:
            await self.queue.put(event)

    async def receive(self) -> SSEEvent:
        """Wait for the next event from the queue."""
        return await self.queue.get()

    def close(self) -> None:
        """Mark the client as closed."""
        self._closed = True

    @property
    def closed(self) -> bool:
        return self._closed

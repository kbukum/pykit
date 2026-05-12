"""SSE client with bounded queue-based event delivery."""

from __future__ import annotations

import asyncio
from typing import Any

from pykit_sse.event import SSEEvent


class SSEClient:
    """A connected SSE client with bounded, non-blocking event delivery."""

    def __init__(
        self,
        client_id: str,
        metadata: dict[str, Any] | None = None,
        *,
        max_queue_size: int = 100,
    ) -> None:
        self.client_id = client_id
        self.metadata: dict[str, Any] = metadata or {}
        self.max_queue_size = max(max_queue_size, 1)
        self.queue: asyncio.Queue[SSEEvent] = asyncio.Queue(maxsize=self.max_queue_size)
        self._closed = False
        self._dropped_events = 0

    async def send(self, event: SSEEvent) -> None:
        """Put *event* onto the client queue without unbounded buffering."""
        if self._closed:
            return
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            _ = self.queue.get_nowait()
            self._dropped_events += 1
            self.queue.put_nowait(event)

    async def receive(self) -> SSEEvent:
        """Wait for the next event from the queue."""
        return await self.queue.get()

    def close(self) -> None:
        """Mark the client as closed."""
        self._closed = True

    @property
    def dropped_events(self) -> int:
        """Number of dropped events due to queue backpressure."""
        return self._dropped_events

    @property
    def closed(self) -> bool:
        return self._closed

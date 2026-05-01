"""Tests for bounded SSE client backpressure."""

from __future__ import annotations

import pytest

from pykit_sse import SSEClient, SSEEvent, SSEHub


@pytest.mark.asyncio
async def test_slow_subscriber_queue_is_bounded() -> None:
    hub = SSEHub()
    slow = SSEClient("slow", max_queue_size=100)
    hub.register(slow)

    for index in range(150):
        await hub.broadcast(SSEEvent(data=str(index)))

    assert slow.queue.qsize() == 100
    assert slow.dropped_events == 50
    first = await slow.receive()
    assert first.data == "50"

"""In-memory message broker for testing."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import UTC, datetime

from pykit_messaging.types import Event, Message, MessageHandler


class InMemoryBroker:
    """Channel-based message broker for testing."""

    def __init__(self, capacity: int = 256) -> None:
        self._queues: dict[str, asyncio.Queue[Message]] = defaultdict(lambda: asyncio.Queue(maxsize=capacity))
        self._capacity = capacity

    def producer(self) -> InMemoryProducer:
        return InMemoryProducer(self._queues)

    def consumer(self, topics: list[str] | None = None) -> InMemoryConsumer:
        return InMemoryConsumer(self._queues, topics or [])


class InMemoryProducer:
    """Implements MessageProducer protocol using in-memory queues."""

    def __init__(self, queues: dict[str, asyncio.Queue[Message]]) -> None:
        self._queues = queues

    async def send(
        self,
        topic: str,
        value: bytes,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        msg = Message(
            key=key,
            value=value,
            topic=topic,
            partition=0,
            offset=0,
            timestamp=datetime.now(UTC),
            headers=headers or {},
        )
        await self._queues[topic].put(msg)

    async def send_event(self, topic: str, event: Event) -> None:
        await self.send(topic, event.to_json(), key=event.subject or None)

    async def send_json(self, topic: str, data: object, key: str | None = None) -> None:
        value = json.dumps(data, default=str).encode()
        await self.send(topic, value, key=key)

    async def send_batch(self, messages: list[Message]) -> None:
        for msg in messages:
            await self._queues[msg.topic].put(msg)

    async def flush(self) -> None:
        pass  # no-op for in-memory

    async def close(self) -> None:
        pass


class InMemoryConsumer:
    """Implements MessageConsumer protocol using in-memory queues."""

    def __init__(self, queues: dict[str, asyncio.Queue[Message]], topics: list[str]) -> None:
        self._queues = queues
        self._topics = list(topics)
        self._running = False

    async def subscribe(self, topics: list[str]) -> None:
        self._topics = list(topics)

    async def consume(self, handler: MessageHandler) -> None:
        self._running = True
        while self._running:
            for topic in self._topics:
                if topic in self._queues:
                    try:
                        msg = self._queues[topic].get_nowait()
                        await handler(msg)
                    except asyncio.QueueEmpty:
                        pass
            await asyncio.sleep(0.01)

    async def close(self) -> None:
        self._running = False

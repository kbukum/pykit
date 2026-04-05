"""In-memory message broker for testing."""

from __future__ import annotations

import asyncio
import json
import threading
from collections import defaultdict
from datetime import UTC, datetime

from pykit_messaging.types import Event, Message, MessageHandler


class InMemoryBroker:
    """Channel-based message broker for testing.

    Every message published through the broker is recorded in an internal
    history list so that test assertion helpers can inspect what was sent.
    """

    def __init__(self, capacity: int = 256) -> None:
        self._queues: dict[str, asyncio.Queue[Message]] = defaultdict(lambda: asyncio.Queue(maxsize=capacity))
        self._capacity = capacity
        self._history: list[Message] = []
        self._topics: set[str] = set()
        self._lock = threading.Lock()
        self._event = asyncio.Event()

    def producer(self) -> InMemoryProducer:
        """Create a new producer backed by this broker."""
        return InMemoryProducer(self._queues, self)

    def consumer(self, topics: list[str] | None = None) -> InMemoryConsumer:
        """Create a new consumer backed by this broker."""
        return InMemoryConsumer(self._queues, topics or [])

    # ── Message history helpers ──────────────────────────────────────────

    def messages(self, topic: str) -> list[Message]:
        """Return all messages published to *topic*."""
        with self._lock:
            return [m for m in self._history if m.topic == topic]

    def all_messages(self) -> list[Message]:
        """Return all messages published to any topic."""
        with self._lock:
            return list(self._history)

    def message_count(self, topic: str) -> int:
        """Return the number of messages published to *topic*."""
        with self._lock:
            return sum(1 for m in self._history if m.topic == topic)

    def reset(self) -> None:
        """Clear the recorded message history."""
        with self._lock:
            self._history.clear()
        self._event.clear()

    # ── Topic helpers ────────────────────────────────────────────────────

    def create_topic(self, topic: str) -> None:
        """Pre-create a topic so it appears in :meth:`topics`."""
        with self._lock:
            self._topics.add(topic)

    def topics(self) -> list[str]:
        """Return the sorted list of known topics."""
        with self._lock:
            all_topics = set(self._topics)
            for m in self._history:
                all_topics.add(m.topic)
        return sorted(all_topics)

    # ── Internal helpers ─────────────────────────────────────────────────

    def _record(self, msg: Message) -> None:
        """Record a message into history and signal waiters."""
        with self._lock:
            self._history.append(msg)
            self._topics.add(msg.topic)
        self._event.set()
        self._event.clear()


class InMemoryProducer:
    """Implements MessageProducer protocol using in-memory queues."""

    def __init__(
        self,
        queues: dict[str, asyncio.Queue[Message]],
        broker: InMemoryBroker,
    ) -> None:
        self._queues = queues
        self._broker = broker

    async def send(
        self,
        topic: str,
        value: bytes,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send a binary message to *topic*."""
        msg = Message(
            key=key,
            value=value,
            topic=topic,
            partition=0,
            offset=0,
            timestamp=datetime.now(UTC),
            headers=headers or {},
        )
        self._broker._record(msg)
        await self._queues[topic].put(msg)

    async def send_event(self, topic: str, event: Event) -> None:
        """Send a structured event to *topic*."""
        await self.send(topic, event.to_json(), key=event.subject or None)

    async def send_json(self, topic: str, data: object, key: str | None = None) -> None:
        """Send a JSON-serialised payload to *topic*."""
        value = json.dumps(data, default=str).encode()
        await self.send(topic, value, key=key)

    async def send_batch(self, messages: list[Message]) -> None:
        """Send a batch of pre-built messages."""
        for msg in messages:
            self._broker._record(msg)
            await self._queues[msg.topic].put(msg)

    async def flush(self) -> None:
        """No-op for in-memory broker."""

    async def close(self) -> None:
        """No-op for in-memory broker."""


class InMemoryConsumer:
    """Implements MessageConsumer protocol using in-memory queues."""

    def __init__(self, queues: dict[str, asyncio.Queue[Message]], topics: list[str]) -> None:
        self._queues = queues
        self._topics = list(topics)
        self._running = False

    async def subscribe(self, topics: list[str]) -> None:
        """Subscribe to the given topics."""
        self._topics = list(topics)

    async def consume(self, handler: MessageHandler) -> None:
        """Consume messages and dispatch to *handler*."""
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
        """Stop the consume loop."""
        self._running = False

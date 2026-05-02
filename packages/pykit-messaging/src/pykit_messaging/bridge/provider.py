"""Bridge adapters between pykit-messaging and pykit-provider."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any

from pykit_messaging.protocols import MessageConsumer, MessageProducer
from pykit_messaging.types import Message

try:
    from pykit_provider import BoxIterator
except ImportError as _err:
    raise ImportError(
        "pykit-provider is required for pykit_messaging.bridge.provider — "
        "install with: pip install pykit-messaging[bridges]"
    ) from _err


class ProducerSink:
    """Wraps a MessageProducer as a provider ``Sink[Message]``.

    Adapts the messaging producer to satisfy the pykit-provider Sink protocol,
    allowing message producers to be used in provider-based architectures.

    Args:
        name: Unique name for this sink provider.
        producer: The message producer to wrap.
        topic: The topic to publish messages to.
    """

    def __init__(self, name: str, producer: MessageProducer, topic: str) -> None:
        self._name = name
        self._producer = producer
        self._topic = topic

    @property
    def name(self) -> str:
        """Return the provider's unique name."""
        return self._name

    async def is_available(self) -> bool:
        """Check if the producer is ready."""
        return True

    async def send(self, input: Message) -> None:
        """Send a message through the wrapped producer.

        Args:
            input: The message to publish.
        """
        await self._producer.send(
            self._topic,
            input.value,
            key=input.key,
            headers=input.headers if input.headers else None,
        )


class _ConsumerBoxIterator(BoxIterator[Message]):
    """Async iterator that pulls messages from a consumer via a queue."""

    def __init__(self, consumer: MessageConsumer) -> None:
        self._consumer = consumer
        self._queue: asyncio.Queue[Message | None] = asyncio.Queue()
        self._task: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        """Start the background consume loop."""
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        async def _handler(msg: Message) -> None:
            await self._queue.put(msg)

        try:
            await self._consumer.consume(_handler)
        finally:
            await self._queue.put(None)

    async def next(self) -> Message | None:
        """Return the next message, or ``None`` when exhausted."""
        return await self._queue.get()

    async def close(self) -> None:
        """Stop consuming and release resources."""
        await self._consumer.close()
        if self._task and not self._task.done():
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task


class ConsumerStream:
    """Wraps a MessageConsumer as a ``Stream[None, Message]``.

    Adapts the messaging consumer to satisfy the pykit-provider Stream
    protocol, allowing message consumers to be used in provider-based
    architectures.

    Args:
        name: Unique name for this stream provider.
        consumer: The message consumer to wrap.
    """

    def __init__(self, name: str, consumer: MessageConsumer) -> None:
        self._name = name
        self._consumer = consumer

    @property
    def name(self) -> str:
        """Return the provider's unique name."""
        return self._name

    async def is_available(self) -> bool:
        """Check if the consumer is ready."""
        return True

    async def execute(self, input: None) -> BoxIterator[Message]:
        """Start consuming and return a stream of messages.

        Args:
            input: Unused (always ``None`` for consumer streams).

        Returns:
            An async iterator yielding messages from the consumer.
        """
        it = _ConsumerBoxIterator(self._consumer)
        await it.start()
        return it

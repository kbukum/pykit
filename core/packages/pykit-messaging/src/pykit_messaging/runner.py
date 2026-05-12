"""Consumer runner for asyncio task management."""

from __future__ import annotations

import asyncio
import logging

from pykit_messaging.handler import MessageHandlerProtocol
from pykit_messaging.protocols import MessageConsumer
from pykit_messaging.types import Message

logger = logging.getLogger(__name__)


class ConsumerRunner:
    """Manages the consumption loop as an asyncio task.

    Provides a blocking ``run`` coroutine that consumes messages until
    ``stop`` is called.

    Args:
        consumer: The consumer to drive.
        handler: The handler to dispatch messages to.
    """

    def __init__(self, consumer: MessageConsumer, handler: MessageHandlerProtocol) -> None:
        self._consumer = consumer
        self._handler = handler
        self._running = False
        self._stop_event = asyncio.Event()

    async def run(self) -> None:
        """Start the consumption loop (blocks until stopped).

        Raises:
            RuntimeError: If the runner is already running.
        """
        if self._running:
            msg = "ConsumerRunner is already running"
            raise RuntimeError(msg)
        self._running = True
        self._stop_event.clear()
        logger.debug("ConsumerRunner started")

        async def _dispatch(msg: Message) -> None:
            await self._handler.handle(msg)

        try:
            await self._consumer.consume(_dispatch)
        except asyncio.CancelledError:
            logger.debug("ConsumerRunner cancelled")
        finally:
            self._running = False
            self._stop_event.set()
            logger.debug("ConsumerRunner stopped")

    async def stop(self) -> None:
        """Stop the consumption loop gracefully."""
        if not self._running:
            return
        await self._consumer.close()
        await self._stop_event.wait()

    @property
    def is_running(self) -> bool:
        """Whether the runner is currently running."""
        return self._running

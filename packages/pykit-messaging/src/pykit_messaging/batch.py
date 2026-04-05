"""Batch producer that collects messages and flushes in batches."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from dataclasses import dataclass

from pykit_messaging.protocols import MessageProducer
from pykit_messaging.types import Message

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchConfig:
    """Configuration for the batch producer.

    Args:
        max_size: Maximum number of messages before an automatic flush.
        max_wait: Maximum seconds between flushes (periodic timer).
        max_bytes: Maximum total bytes before an automatic flush. 0 means unlimited.
    """

    max_size: int = 100
    max_wait: float = 5.0
    max_bytes: int = 0


class BatchProducer:
    """Collects messages and flushes them to an underlying producer in batches.

    Batches are flushed when any configured limit is reached (size, bytes) or
    when the periodic timer fires.

    Args:
        producer: The underlying producer to delegate batch sends to.
        topic: Default topic for buffered messages.
        config: Optional batch configuration; defaults to ``BatchConfig()``.
    """

    def __init__(
        self,
        producer: MessageProducer,
        topic: str,
        config: BatchConfig | None = None,
    ) -> None:
        self._producer = producer
        self._topic = topic
        self._config = config or BatchConfig()
        self._buffer: list[Message] = []
        self._buffer_bytes: int = 0
        self._lock = asyncio.Lock()
        self._timer_task: asyncio.Task[None] | None = None
        self._closed = False
        self._start_timer()

    def _start_timer(self) -> None:
        """Start the periodic flush timer."""
        if self._config.max_wait > 0:
            self._timer_task = asyncio.get_event_loop().create_task(self._periodic_flush())

    async def _periodic_flush(self) -> None:
        """Periodically flush the buffer based on ``max_wait``."""
        try:
            while not self._closed:
                await asyncio.sleep(self._config.max_wait)
                async with self._lock:
                    if self._buffer:
                        await self._do_flush()
        except asyncio.CancelledError:
            pass

    async def send(self, msg: Message) -> None:
        """Buffer a message. Auto-flushes when configured limits are reached.

        Args:
            msg: The message to buffer.

        Raises:
            RuntimeError: If the batch producer has been closed.
        """
        if self._closed:
            msg_text = "BatchProducer is closed"
            raise RuntimeError(msg_text)

        async with self._lock:
            self._buffer.append(msg)
            self._buffer_bytes += len(msg.value)

            should_flush = len(self._buffer) >= self._config.max_size
            if not should_flush and self._config.max_bytes > 0:
                should_flush = self._buffer_bytes >= self._config.max_bytes

            if should_flush:
                await self._do_flush()

    async def flush(self) -> None:
        """Force flush all buffered messages."""
        async with self._lock:
            if self._buffer:
                await self._do_flush()

    async def close(self) -> None:
        """Flush remaining messages and stop the background flush timer."""
        self._closed = True
        if self._timer_task is not None:
            self._timer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._timer_task
            self._timer_task = None
        await self.flush()

    async def _do_flush(self) -> None:
        """Flush the current buffer via the underlying producer."""
        if not self._buffer:
            return
        batch = list(self._buffer)
        self._buffer.clear()
        self._buffer_bytes = 0
        await self._producer.send_batch(batch)

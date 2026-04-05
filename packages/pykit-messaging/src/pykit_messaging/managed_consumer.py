"""Managed consumer with lifecycle, handler dispatch, and graceful shutdown."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

from pykit_messaging.handler import MessageHandlerProtocol
from pykit_messaging.metrics import MetricsCollector, NoopMetrics
from pykit_messaging.protocols import MessageConsumer
from pykit_messaging.types import Message

logger = logging.getLogger(__name__)


class ManagedConsumer:
    """Wraps a MessageConsumer with lifecycle, handler dispatch, and graceful shutdown.

    Args:
        inner: The underlying consumer to delegate to.
        handler: The handler to dispatch messages to.
        name: A human-readable name for logging.
        metrics: Optional metrics collector; defaults to NoopMetrics.
    """

    def __init__(
        self,
        inner: MessageConsumer,
        handler: MessageHandlerProtocol,
        name: str,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self._inner = inner
        self._handler = handler
        self._name = name
        self._metrics: MetricsCollector = metrics or NoopMetrics()
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the consumption loop as an asyncio task.

        Raises:
            RuntimeError: If the consumer is already running.
        """
        if self._running:
            msg = f"Consumer '{self._name}' is already running"
            raise RuntimeError(msg)
        self._running = True
        self._task = asyncio.create_task(self._consume_loop(), name=f"consumer-{self._name}")
        logger.info("Consumer '%s' started", self._name)

    async def stop(self) -> None:
        """Stop consumption with graceful shutdown."""
        if not self._running:
            return
        self._running = False
        await self._inner.close()
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Consumer '%s' stopped", self._name)

    @property
    def is_running(self) -> bool:
        """Whether the consumer is currently running."""
        return self._running

    async def _consume_loop(self) -> None:
        """Internal consumption loop that wraps the handler with metrics."""

        async def _metered_handler(msg: Message) -> None:
            start = time.monotonic()
            success = True
            try:
                await self._handler.handle(msg)
            except Exception:
                success = False
                raise
            finally:
                duration_ms = (time.monotonic() - start) * 1000
                self._metrics.record_consume(msg.topic, duration_ms, success=success)

        try:
            await self._inner.consume(_metered_handler)
        except asyncio.CancelledError:
            logger.debug("Consumer '%s' consumption loop cancelled", self._name)
        except Exception:
            logger.exception("Consumer '%s' consumption loop failed", self._name)
            self._running = False

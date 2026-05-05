"""Managed producer with lifecycle management and metrics."""

from __future__ import annotations

import logging
import time

from pykit_messaging.metrics import MetricsCollector, NoopMetrics
from pykit_messaging.protocols import MessageProducer
from pykit_messaging.types import Event, JsonValue, Message

logger = logging.getLogger(__name__)


class ManagedProducer:
    """Wraps a MessageProducer with lifecycle management and metrics.

    Args:
        inner: The underlying producer to delegate to.
        name: A human-readable name for logging.
        metrics: Optional metrics collector; defaults to NoopMetrics.
    """

    def __init__(
        self,
        inner: MessageProducer,
        name: str,
        metrics: MetricsCollector | None = None,
    ) -> None:
        self._inner = inner
        self._name = name
        self._metrics: MetricsCollector = metrics or NoopMetrics()
        self._running = False

    async def start(self) -> None:
        """Mark the producer as running.

        Raises:
            RuntimeError: If the producer is already running.
        """
        if self._running:
            msg = f"Producer '{self._name}' is already running"
            raise RuntimeError(msg)
        self._running = True
        logger.debug("Producer '%s' started", self._name)

    async def stop(self) -> None:
        """Stop the producer and close the inner producer."""
        if not self._running:
            return
        self._running = False
        await self._inner.close()
        logger.debug("Producer '%s' stopped", self._name)

    @property
    def is_running(self) -> bool:
        """Whether the producer is currently running."""
        return self._running

    def _check_running(self) -> None:
        if not self._running:
            msg = f"Producer '{self._name}' is not running"
            raise RuntimeError(msg)

    async def send(
        self,
        topic: str,
        value: bytes,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send a message, recording metrics.

        Args:
            topic: Target topic.
            value: Message payload.
            key: Optional message key.
            headers: Optional message headers.
        """
        self._check_running()
        start = time.monotonic()
        success = True
        try:
            await self._inner.send(topic, value, key=key, headers=headers)
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            self._metrics.record_publish(topic, duration_ms, success=success)

    async def send_event(self, topic: str, event: Event) -> None:
        """Send an event, recording metrics.

        Args:
            topic: Target topic.
            event: The event to send.
        """
        self._check_running()
        start = time.monotonic()
        success = True
        try:
            await self._inner.send_event(topic, event)
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            self._metrics.record_publish(topic, duration_ms, success=success)

    async def send_json(self, topic: str, data: JsonValue, key: str | None = None) -> None:
        """Send JSON data, recording metrics.

        Args:
            topic: Target topic.
            data: Data to serialize as JSON.
            key: Optional message key.
        """
        self._check_running()
        start = time.monotonic()
        success = True
        try:
            await self._inner.send_json(topic, data, key=key)
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            self._metrics.record_publish(topic, duration_ms, success=success)

    async def send_batch(self, messages: list[Message]) -> None:
        """Send a batch of messages, recording metrics.

        Args:
            messages: Messages to send.
        """
        self._check_running()
        start = time.monotonic()
        success = True
        try:
            await self._inner.send_batch(messages)
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.monotonic() - start) * 1000
            topic = messages[0].topic if messages else "unknown"
            self._metrics.record_publish(topic, duration_ms, success=success)

    async def flush(self) -> None:
        """Flush the inner producer."""
        self._check_running()
        await self._inner.flush()

    async def close(self) -> None:
        """Close the managed producer (alias for stop)."""
        await self.stop()

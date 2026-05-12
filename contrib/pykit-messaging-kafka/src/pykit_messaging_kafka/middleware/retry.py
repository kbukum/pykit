"""Retry middleware for Kafka message handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pykit_messaging.types import Message, MessageHandler
from pykit_resilience import RetryConfig as ResilienceRetryConfig
from pykit_resilience import RetryExhaustedError
from pykit_resilience import retry as retry_async


@dataclass
class RetryMiddlewareConfig(ResilienceRetryConfig):
    """Configuration for Kafka retry middleware."""

    on_exhausted: Callable[[Message, Exception], Awaitable[None]] | None = None


def RetryHandler(handler: MessageHandler, config: RetryMiddlewareConfig | None = None) -> MessageHandler:
    """Wrap a MessageHandler with canonical retry behavior.

    Each retry attempt updates the ``x-retry-count`` header on a cloned message.
    """
    cfg = config or RetryMiddlewareConfig()

    async def wrapper(msg: Message) -> None:
        headers = dict(msg.headers)
        cloned = Message(
            key=msg.key,
            value=msg.value,
            topic=msg.topic,
            partition=msg.partition,
            offset=msg.offset,
            timestamp=msg.timestamp,
            headers=headers,
        )
        attempt = 0

        async def _handle() -> None:
            nonlocal attempt
            attempt += 1
            if attempt > 1:
                cloned.headers["x-retry-count"] = str(attempt - 1)
            await handler(cloned)

        try:
            await retry_async(_handle, cfg)
        except RetryExhaustedError as exc:
            if cfg.on_exhausted is not None:
                await cfg.on_exhausted(cloned, exc.last_error)
            raise exc.last_error from exc

    return wrapper

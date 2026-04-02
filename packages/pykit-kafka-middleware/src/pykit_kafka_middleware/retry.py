"""Retry middleware for Kafka message handlers with exponential backoff."""

from __future__ import annotations

import asyncio
import math
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pykit_kafka.types import Message, MessageHandler


@dataclass
class RetryMiddlewareConfig:
    """Configuration for Kafka retry middleware."""

    max_attempts: int = 3
    initial_backoff: float = 0.1
    max_backoff: float = 10.0
    backoff_factor: float = 2.0
    jitter: float = 0.1
    retry_if: Callable[[Exception], bool] | None = None
    on_exhausted: Callable[[Message, Exception], Awaitable[None]] | None = None


def _calculate_backoff(attempt: int, config: RetryMiddlewareConfig) -> float:
    """Calculate backoff duration with exponential growth and jitter."""
    backoff = config.initial_backoff * math.pow(config.backoff_factor, attempt - 1)
    if config.jitter > 0:
        jitter_range = backoff * config.jitter
        backoff += random.uniform(-jitter_range, jitter_range)
    backoff = min(backoff, config.max_backoff)
    return max(backoff, 0.0)


def RetryHandler(handler: MessageHandler, config: RetryMiddlewareConfig | None = None) -> MessageHandler:
    """Wrap a MessageHandler with retry logic using exponential backoff.

    Each retry attempt updates the ``x-retry-count`` header on the message.
    When all attempts are exhausted, ``config.on_exhausted`` is invoked
    (e.g. for DLQ routing) and the last error is returned.
    """
    cfg = config or RetryMiddlewareConfig()

    async def wrapper(msg: Message) -> None:
        headers = dict(msg.headers)
        msg = Message(
            key=msg.key,
            value=msg.value,
            topic=msg.topic,
            partition=msg.partition,
            offset=msg.offset,
            timestamp=msg.timestamp,
            headers=headers,
        )

        last_error: Exception | None = None
        for attempt in range(1, cfg.max_attempts + 1):
            try:
                if attempt > 1:
                    msg.headers["x-retry-count"] = str(attempt - 1)
                await handler(msg)
                return
            except Exception as exc:
                last_error = exc
                if cfg.retry_if is not None and not cfg.retry_if(exc):
                    raise
                if attempt < cfg.max_attempts:
                    backoff = _calculate_backoff(attempt, cfg)
                    await asyncio.sleep(backoff)

        if cfg.on_exhausted is not None and last_error is not None:
            await cfg.on_exhausted(msg, last_error)

        if last_error is not None:
            raise last_error

    return wrapper

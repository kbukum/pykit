"""Retry middleware for message handlers."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pykit_messaging.handler import MessageHandlerProtocol
from pykit_messaging.types import Message


@dataclass(frozen=True)
class RetryConfig:
    """Configuration for retry middleware.

    Args:
        max_attempts: Maximum number of retry attempts (including initial attempt).
        initial_backoff: Initial backoff duration in seconds.
        max_backoff: Maximum backoff duration in seconds.
        backoff_factor: Exponential backoff multiplier per attempt.
        jitter: Jitter range as fraction of backoff (0.1 = ±10%).
        on_exhausted: Optional callback when all retries are exhausted.
    """

    max_attempts: int = 3
    initial_backoff: float = 0.1
    max_backoff: float = 10.0
    backoff_factor: float = 2.0
    jitter: float = 0.1
    on_exhausted: Callable[[Message, Exception], Awaitable[None]] | None = None


class RetryHandler:
    """Retries failed message handling with exponential backoff.

    After all attempts are exhausted, calls ``on_exhausted`` (if set)
    and re-raises the last exception.

    Args:
        inner: The handler to delegate to.
        config: Optional retry configuration; defaults to ``RetryConfig()``.
    """

    def __init__(
        self,
        inner: MessageHandlerProtocol,
        config: RetryConfig | None = None,
    ) -> None:
        self._inner = inner
        self._config = config or RetryConfig()

    async def handle(self, msg: Message) -> None:
        """Handle a message with retry logic.

        Args:
            msg: The message to handle.

        Raises:
            The last exception encountered if all retries are exhausted.
        """
        cfg = self._config
        last_err: Exception | None = None
        backoff = cfg.initial_backoff

        for attempt in range(cfg.max_attempts):
            try:
                await self._inner.handle(msg)
                return
            except Exception as exc:
                last_err = exc
                if attempt < cfg.max_attempts - 1:
                    jittered = backoff * (1 + random.uniform(-cfg.jitter, cfg.jitter))
                    await asyncio.sleep(jittered)
                    backoff = min(backoff * cfg.backoff_factor, cfg.max_backoff)

        if last_err is not None:
            if cfg.on_exhausted is not None:
                await cfg.on_exhausted(msg, last_err)
            raise last_err


def retry(
    config: RetryConfig | None = None,
) -> Callable[[MessageHandlerProtocol], MessageHandlerProtocol]:
    """Return a middleware function implementing exponential backoff retry logic.

    Args:
        config: Optional retry configuration.

    Returns:
        A middleware function compatible with ``chain_handlers``.
    """

    def _middleware(handler: MessageHandlerProtocol) -> MessageHandlerProtocol:
        return RetryHandler(handler, config)

    return _middleware

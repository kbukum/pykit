"""Retry middleware for message handlers."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pykit_messaging.handler import MessageHandlerProtocol
from pykit_messaging.types import Message
from pykit_resilience import RetryConfig as ResilienceRetryConfig
from pykit_resilience import RetryExhaustedError
from pykit_resilience import retry as retry_async


@dataclass
class RetryConfig(ResilienceRetryConfig):
    """Configuration for retry middleware."""

    on_exhausted: Callable[[Message, Exception], Awaitable[None]] | None = None


class RetryHandler:
    """Retries failed message handling using pykit-resilience."""

    def __init__(
        self,
        inner: MessageHandlerProtocol,
        config: RetryConfig | None = None,
    ) -> None:
        self._inner = inner
        self._config = config or RetryConfig()

    async def handle(self, msg: Message) -> None:
        """Handle a message with retry logic."""
        cfg = self._config

        async def _handle() -> None:
            await self._inner.handle(msg)

        try:
            await retry_async(_handle, cfg)
        except RetryExhaustedError as exc:
            if cfg.on_exhausted is not None:
                await cfg.on_exhausted(msg, exc.last_error)
            # Always re-raise terminal error so outer middleware (circuit breaker, metrics)
            # knows this was a failure, even if on_exhausted() succeeds (e.g., DLQ handling).
            raise exc.last_error from exc


def retry(
    config: RetryConfig | None = None,
) -> Callable[[MessageHandlerProtocol], MessageHandlerProtocol]:
    """Return a middleware function implementing canonical retry behavior."""

    def _middleware(handler: MessageHandlerProtocol) -> MessageHandlerProtocol:
        return RetryHandler(handler, config)

    return _middleware

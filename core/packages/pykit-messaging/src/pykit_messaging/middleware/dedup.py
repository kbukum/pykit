"""Deduplication middleware for message handlers."""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from pykit_messaging.handler import MessageHandlerProtocol
from pykit_messaging.types import Message

logger = logging.getLogger(__name__)


def _default_key_func(msg: Message) -> str:
    """Extract dedup key from the ``message-id`` header or fall back to offset."""
    msg_id = msg.headers.get("message-id")
    if msg_id:
        return msg_id
    return f"{msg.topic}:{msg.partition}:{msg.offset}"


@dataclass(frozen=True)
class DedupConfig:
    """Configuration for deduplication middleware.

    Args:
        key_func: Function to extract a dedup key from a message.
            Defaults to the ``message-id`` header.
        window_size: Maximum number of keys to keep in the dedup window.
        ttl: Time-to-live in seconds for dedup entries.
    """

    key_func: Callable[[Message], str] | None = None
    window_size: int = 10000
    ttl: float = 300.0


class DedupHandler:
    """Skips duplicate messages by key within a sliding window.

    Args:
        inner: The handler to delegate non-duplicate messages to.
        config: Optional dedup configuration; defaults to ``DedupConfig()``.
    """

    def __init__(
        self,
        inner: MessageHandlerProtocol,
        config: DedupConfig | None = None,
    ) -> None:
        self._inner = inner
        self._config = config or DedupConfig()
        self._key_func = self._config.key_func or _default_key_func
        self._seen: OrderedDict[str, float] = OrderedDict()

    async def handle(self, msg: Message) -> None:
        """Handle a message, skipping duplicates.

        Args:
            msg: The message to handle.
        """
        key = self._key_func(msg)
        now = time.monotonic()

        self._evict_expired(now)

        if key in self._seen:
            logger.debug("Duplicate message skipped: %s", key)
            return

        self._seen[key] = now

        # Evict oldest entries if window is full
        while len(self._seen) > self._config.window_size:
            self._seen.popitem(last=False)

        await self._inner.handle(msg)

    def _evict_expired(self, now: float) -> None:
        """Remove entries older than TTL from the front of the window."""
        cutoff = now - self._config.ttl
        while self._seen:
            _oldest_key, oldest_time = next(iter(self._seen.items()))
            if oldest_time <= cutoff:
                self._seen.popitem(last=False)
            else:
                break


def dedup(
    config: DedupConfig | None = None,
) -> Callable[[MessageHandlerProtocol], MessageHandlerProtocol]:
    """Return a middleware function that wraps a handler with deduplication.

    Args:
        config: Optional dedup configuration.

    Returns:
        A middleware function compatible with ``chain_handlers``.
    """

    def _middleware(inner: MessageHandlerProtocol) -> MessageHandlerProtocol:
        return DedupHandler(inner, config)

    return _middleware

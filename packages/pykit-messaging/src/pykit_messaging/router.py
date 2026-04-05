"""Message router for topic-based handler dispatch."""

from __future__ import annotations

import fnmatch
import logging

from pykit_messaging.handler import FuncHandler, MessageHandlerProtocol
from pykit_messaging.types import Message

logger = logging.getLogger(__name__)


class MessageRouter:
    """Routes messages to handlers based on topic patterns.

    Supports exact topic matching and wildcard patterns using ``fnmatch``
    style globs (e.g. ``"content.*"``).  The first matching pattern wins.

    Example::

        router = MessageRouter()
        router.handle("orders.*", order_handler)
        router.handle("users.created", user_handler)
        router.default(fallback_handler)

        handler = router.as_handler()
        await handler.handle(msg)
    """

    def __init__(self) -> None:
        self._routes: list[tuple[str, MessageHandlerProtocol]] = []
        self._default: MessageHandlerProtocol | None = None

    def handle(self, pattern: str, handler: MessageHandlerProtocol) -> MessageRouter:
        """Register a handler for a topic pattern.

        Args:
            pattern: Exact topic name or wildcard pattern (e.g. ``"content.*"``).
            handler: Handler to invoke for matching messages.

        Returns:
            Self for fluent chaining.
        """
        self._routes.append((pattern, handler))
        return self

    def default(self, handler: MessageHandlerProtocol) -> MessageRouter:
        """Set fallback handler for unmatched messages.

        Args:
            handler: Handler to invoke when no pattern matches.

        Returns:
            Self for fluent chaining.
        """
        self._default = handler
        return self

    def as_handler(self) -> MessageHandlerProtocol:
        """Return a ``MessageHandlerProtocol`` that routes based on registered patterns.

        Returns:
            A handler that dispatches to the first matching registered handler.
        """
        routes = list(self._routes)
        default = self._default

        async def _dispatch(msg: Message) -> None:
            topic = msg.topic
            for pattern, handler in routes:
                if pattern == topic or fnmatch.fnmatch(topic, pattern):
                    await handler.handle(msg)
                    return
            if default is not None:
                await default.handle(msg)
                return
            logger.warning("No handler matched topic '%s'", topic)

        return FuncHandler(_dispatch)

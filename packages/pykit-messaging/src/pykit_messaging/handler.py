"""Handler chain types and middleware composition."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol, runtime_checkable

from pykit_messaging.types import Message


@runtime_checkable
class MessageHandlerProtocol(Protocol):
    """Protocol for message handlers with a structured handle method."""

    async def handle(self, msg: Message) -> None:
        """Handle a single message.

        Args:
            msg: The message to handle.
        """
        ...


HandlerMiddleware = Callable[[MessageHandlerProtocol], MessageHandlerProtocol]
"""A middleware that wraps a handler to add cross-cutting behavior."""


def chain_handlers(
    base: MessageHandlerProtocol,
    *middlewares: HandlerMiddleware,
) -> MessageHandlerProtocol:
    """Chain middleware around a base handler.

    Middlewares are applied in order so the first middleware is the outermost
    wrapper. For example, ``chain_handlers(h, m1, m2)`` produces
    ``m2(m1(h))`` — m2 runs first on each message, then m1, then h.

    Args:
        base: The innermost handler to wrap.
        *middlewares: Middleware functions to apply in order.

    Returns:
        The fully wrapped handler.
    """
    result = base
    for mw in middlewares:
        result = mw(result)
    return result


class FuncHandler:
    """Adapts a callable to MessageHandlerProtocol.

    Args:
        func: An async callable that accepts a Message and returns None.
    """

    def __init__(self, func: Callable[[Message], Awaitable[None]]) -> None:
        self._func = func

    async def handle(self, msg: Message) -> None:
        """Handle a message by delegating to the wrapped function.

        Args:
            msg: The message to handle.
        """
        await self._func(msg)

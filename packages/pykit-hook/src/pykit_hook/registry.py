"""Registry — subscribe to and emit lifecycle events."""

from __future__ import annotations

import inspect
from collections import defaultdict
from collections.abc import Awaitable, Callable

from pykit_hook.types import (
    Action,
    Event,
    EventType,
    Handler,
    HookContext,
    Result,
    continue_with_error,
)

type HandlerResult = Result | Awaitable[Result]


class Registry:
    """Central registry for hook event handlers.

    Handlers are executed sequentially in registration order.
    The first ``ABORT`` short-circuits; ``MODIFY`` results chain so each
    handler sees the previous handler's modifications.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[Handler]] = defaultdict(list)

    def on(self, event_type: EventType, handler: Handler) -> Callable[[], None]:
        """Register a handler for an event type.

        Args:
            event_type: The event type to listen for.
            handler: The handler function.

        Returns:
            An unsubscribe function that removes the handler.
        """
        self._handlers[event_type].append(handler)

        def unsubscribe() -> None:
            handlers = self._handlers.get(event_type)
            if handlers and handler in handlers:
                handlers.remove(handler)

        return unsubscribe

    def emit(
        self,
        event: Event,
        context: HookContext | None = None,
        *,
        reverse: bool = False,
    ) -> Result:
        """Emit an event and run all registered handlers sequentially.

        Args:
            event: The hook event to emit.
            context: Optional context forwarded to context-aware handlers.
            reverse: Whether to traverse handlers in reverse registration order.

        Returns:
            Aggregated hook result.
        """
        last_result = Result()
        for handler in self._iter_handlers(event.type, reverse=reverse):
            try:
                result: Result = self._invoke_handler(handler, event, context)  # type: ignore[assignment]
            except Exception as exc:
                result = continue_with_error(exc)

            if result.action == Action.ABORT:
                return result
            if result.action != Action.CONTINUE or result.error is not None:
                last_result = result
        return last_result

    async def emit_async(
        self,
        event: Event,
        context: HookContext | None = None,
        *,
        reverse: bool = False,
    ) -> Result:
        """Emit an event and await any async handlers.

        Args:
            event: The hook event to emit.
            context: Optional context forwarded to context-aware handlers.
            reverse: Whether to traverse handlers in reverse registration order.

        Returns:
            Aggregated hook result.
        """
        last_result = Result()
        for handler in self._iter_handlers(event.type, reverse=reverse):
            try:
                outcome = self._invoke_handler(handler, event, context)
                if inspect.isawaitable(outcome):
                    result: Result = await outcome
                else:
                    result = outcome
            except Exception as exc:
                result = continue_with_error(exc)

            if result.action == Action.ABORT:
                return result
            if result.action != Action.CONTINUE or result.error is not None:
                last_result = result
        return last_result

    def has_handlers(self, event_type: EventType) -> bool:
        """Check if any handlers are registered for an event type."""
        return len(self._handlers.get(event_type, [])) > 0

    def clear(self, *event_types: EventType) -> None:
        """Clear handlers for the given event types, or all handlers if none specified."""
        if event_types:
            for et in event_types:
                self._handlers.pop(et, None)
        else:
            self._handlers.clear()

    def _iter_handlers(self, event_type: EventType, *, reverse: bool = False) -> list[Handler]:
        handlers = list(self._handlers.get(event_type, []))
        if reverse:
            handlers.reverse()
        return handlers

    @staticmethod
    def _invoke_handler(
        handler: Handler,
        event: Event,
        context: HookContext | None,
    ) -> HandlerResult:
        signature = inspect.signature(handler)
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        if (
            any(
                parameter.kind == inspect.Parameter.VAR_POSITIONAL
                for parameter in signature.parameters.values()
            )
            or len(positional) >= 2
        ):
            return handler(context, event)
        return handler(event)


HookRegistry = Registry

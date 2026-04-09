"""HookRegistry — subscribe to and emit lifecycle events."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from pykit_hook.types import Action, EventType, HookEvent, HookHandler, HookResult


class HookRegistry:
    """Central registry for hook event handlers.

    Handlers are executed sequentially in registration order.
    The first ``ABORT`` short-circuits; ``MODIFY`` results chain so each
    handler sees the previous handler's modifications.
    """

    def __init__(self) -> None:
        self._handlers: dict[EventType, list[HookHandler]] = defaultdict(list)

    def on(self, event_type: EventType, handler: HookHandler) -> Callable[[], None]:
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

    def emit(self, event: HookEvent) -> HookResult:
        """Emit an event and run all registered handlers sequentially.

        - First ``ABORT`` result short-circuits and returns immediately.
        - ``MODIFY`` results chain: the ``modified_data`` is carried forward.
        - If no handlers return ``ABORT`` or ``MODIFY``, returns ``CONTINUE``.

        Args:
            event: The hook event to emit.

        Returns:
            Aggregated hook result.
        """
        handlers = self._handlers.get(event.type, [])
        last_result = HookResult()
        for handler in handlers:
            result = handler(event)
            if result.action == Action.ABORT:
                return result
            if result.action == Action.MODIFY:
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

"""pykit-hook — Generic event hook system."""

from pykit_hook.registry import HookRegistry, Registry
from pykit_hook.types import (
    Action,
    Event,
    EventType,
    Handler,
    HookContext,
    HookEvent,
    HookHandler,
    HookResult,
    Result,
    abort,
    abort_with_error,
    continue_,
    continue_with_error,
    modify,
)

__all__ = [
    "Action",
    "Event",
    "EventType",
    "Handler",
    "HookContext",
    "HookEvent",
    "HookHandler",
    "HookRegistry",
    "HookResult",
    "Registry",
    "Result",
    "abort",
    "abort_with_error",
    "continue_",
    "continue_with_error",
    "modify",
]

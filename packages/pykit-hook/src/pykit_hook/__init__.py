"""pykit-hook — Generic event hook system."""

from pykit_hook.registry import HookRegistry, Registry
from pykit_hook.types import (
    Action,
    Event,
    EventType,
    Handler,
    HookEvent,
    HookHandler,
    HookResult,
    Result,
    abort,
    continue_,
    modify,
)

__all__ = [
    "Action",
    "Event",
    "EventType",
    "Handler",
    "HookEvent",
    "HookHandler",
    "HookRegistry",
    "HookResult",
    "Registry",
    "Result",
    "abort",
    "continue_",
    "modify",
]

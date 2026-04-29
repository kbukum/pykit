"""Generic hook primitives — event system with zero domain dependencies."""

from __future__ import annotations

import enum
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

EventType = str
"""String identifier for an event category (e.g. ``"pre_tool_call"``)."""

type HookContext = dict[str, object] | object
"""Optional context passed to handlers during emission."""


@runtime_checkable
class Event(Protocol):
    """Any object with a ``type`` attribute is a valid hook event."""

    @property
    def type(self) -> EventType: ...


class Action(enum.Enum):
    """What to do after a hook handler runs."""

    CONTINUE = "continue"
    ABORT = "abort"
    MODIFY = "modify"


@dataclass(frozen=True)
class Result:
    """Result returned by a hook handler."""

    action: Action = Action.CONTINUE
    modified_data: object | None = None
    reason: str = ""
    error: Exception | None = None


# Handler is any callable — the registry inspects the signature at runtime
# to decide whether to pass (event,) or (context, event).
type Handler = Callable[..., Result | Awaitable[Result]]


def continue_() -> Result:
    """Return a CONTINUE result."""
    return Result()


def continue_with_error(err: Exception) -> Result:
    """Return a CONTINUE result that records an error."""
    return Result(reason=str(err), error=err)


def abort(reason: str = "") -> Result:
    """Return an ABORT result."""
    return Result(action=Action.ABORT, reason=reason)


def abort_with_error(err: Exception) -> Result:
    """Return an ABORT result that records an error."""
    return Result(action=Action.ABORT, reason=str(err), error=err)


def modify(data: object, reason: str = "") -> Result:
    """Return a MODIFY result."""
    return Result(action=Action.MODIFY, modified_data=data, reason=reason)


HookEvent = Event
HookResult = Result
HookHandler = Handler

"""Generic hook primitives — event system with zero domain dependencies."""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

# ---------------------------------------------------------------------------
# Event type alias
# ---------------------------------------------------------------------------

EventType = str
"""String identifier for an event category (e.g. ``"pre_tool_call"``)."""

# ---------------------------------------------------------------------------
# Event protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class Event(Protocol):
    """Any object with a ``type`` attribute is a valid hook event."""

    type: EventType


# ---------------------------------------------------------------------------
# Action / Result
# ---------------------------------------------------------------------------


class Action(enum.Enum):
    """What to do after a hook handler runs."""

    CONTINUE = "continue"
    ABORT = "abort"
    MODIFY = "modify"


@dataclass
class Result:
    """Result returned by a hook handler."""

    action: Action = Action.CONTINUE
    modified_data: Any = None
    reason: str = ""


# ---------------------------------------------------------------------------
# Handler type
# ---------------------------------------------------------------------------

Handler = Callable[[Event], Result]

# ---------------------------------------------------------------------------
# Convenience factories
# ---------------------------------------------------------------------------


def continue_() -> Result:
    """Return a CONTINUE result."""
    return Result()


def abort(reason: str = "") -> Result:
    """Return an ABORT result."""
    return Result(action=Action.ABORT, reason=reason)


def modify(data: Any, reason: str = "") -> Result:
    """Return a MODIFY result."""
    return Result(action=Action.MODIFY, modified_data=data, reason=reason)


# ---------------------------------------------------------------------------
# Backwards-compatible aliases
# ---------------------------------------------------------------------------

HookEvent = Event
HookResult = Result
HookHandler = Handler

"""Hook event types for agentic system lifecycle."""

from __future__ import annotations

import enum
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pykit_llm.types import AssistantMessage, CompletionRequest, CompletionResponse

# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class EventType(enum.StrEnum):
    """Hook event categories."""

    PRE_TOOL_CALL = "pre_tool_call"
    POST_TOOL_CALL = "post_tool_call"
    PRE_LLM_CALL = "pre_llm_call"
    POST_LLM_CALL = "post_llm_call"
    ON_ERROR = "on_error"
    TURN_START = "turn_start"
    TURN_END = "turn_end"


# ---------------------------------------------------------------------------
# Hook events — discriminated union
# ---------------------------------------------------------------------------


@dataclass
class HookEvent:
    """Base class for all hook events."""

    type: EventType


@dataclass
class PreToolCall(HookEvent):
    """Emitted before a tool is called."""

    name: str = ""
    input: Any = None


@dataclass
class PostToolCall(HookEvent):
    """Emitted after a tool call completes."""

    name: str = ""
    input: Any = None
    result: Any = None
    error: Exception | None = None


@dataclass
class PreLLMCall(HookEvent):
    """Emitted before an LLM completion is requested."""

    request: CompletionRequest = field(default_factory=lambda: CompletionRequest(messages=[]))


@dataclass
class PostLLMCall(HookEvent):
    """Emitted after an LLM completion returns."""

    response: CompletionResponse = field(
        default_factory=lambda: CompletionResponse(message=AssistantMessage())
    )
    error: Exception | None = None


@dataclass
class OnError(HookEvent):
    """Emitted when an error occurs."""

    error: Exception = field(default_factory=Exception)
    source: str = ""


@dataclass
class TurnStart(HookEvent):
    """Emitted at the beginning of an agent turn."""

    turn: int = 0


@dataclass
class TurnEnd(HookEvent):
    """Emitted at the end of an agent turn."""

    turn: int = 0
    message: AssistantMessage = field(default_factory=AssistantMessage)


# ---------------------------------------------------------------------------
# Action / Result
# ---------------------------------------------------------------------------


class Action(enum.Enum):
    """What to do after a hook handler runs."""

    CONTINUE = "continue"
    ABORT = "abort"
    MODIFY = "modify"


@dataclass
class HookResult:
    """Result returned by a hook handler."""

    action: Action = Action.CONTINUE
    modified_data: Any = None
    reason: str = ""


# ---------------------------------------------------------------------------
# Handler type
# ---------------------------------------------------------------------------

HookHandler = Callable[[HookEvent], HookResult]

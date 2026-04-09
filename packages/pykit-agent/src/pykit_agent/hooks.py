"""Domain-specific hook event types for the agent lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pykit_llm.types import AssistantMessage, CompletionRequest, CompletionResponse

# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

EVENT_PRE_TOOL_CALL = "pre_tool_call"
EVENT_POST_TOOL_CALL = "post_tool_call"
EVENT_PRE_LLM_CALL = "pre_llm_call"
EVENT_POST_LLM_CALL = "post_llm_call"
EVENT_ON_ERROR = "on_error"
EVENT_TURN_START = "turn_start"
EVENT_TURN_END = "turn_end"

# ---------------------------------------------------------------------------
# Hook events — each satisfies the pykit_hook.Event protocol
# ---------------------------------------------------------------------------


@dataclass
class PreToolCall:
    """Emitted before a tool is called."""

    name: str = ""
    input: Any = None
    type: str = EVENT_PRE_TOOL_CALL


@dataclass
class PostToolCall:
    """Emitted after a tool call completes."""

    name: str = ""
    input: Any = None
    result: Any = None
    error: Exception | None = None
    type: str = EVENT_POST_TOOL_CALL


@dataclass
class PreLLMCall:
    """Emitted before an LLM completion is requested."""

    request: CompletionRequest = field(default_factory=lambda: CompletionRequest(messages=[]))
    type: str = EVENT_PRE_LLM_CALL


@dataclass
class PostLLMCall:
    """Emitted after an LLM completion returns."""

    response: CompletionResponse = field(
        default_factory=lambda: CompletionResponse(message=AssistantMessage())
    )
    error: Exception | None = None
    type: str = EVENT_POST_LLM_CALL


@dataclass
class OnError:
    """Emitted when an error occurs."""

    error: Exception = field(default_factory=Exception)
    source: str = ""
    type: str = EVENT_ON_ERROR


@dataclass
class TurnStart:
    """Emitted at the beginning of an agent turn."""

    turn: int = 0
    type: str = EVENT_TURN_START


@dataclass
class TurnEnd:
    """Emitted at the end of an agent turn."""

    turn: int = 0
    message: AssistantMessage = field(default_factory=AssistantMessage)
    type: str = EVENT_TURN_END

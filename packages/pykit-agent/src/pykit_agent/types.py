"""Agent types — result, events, context strategies, and errors."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Any, Protocol

from pykit_llm.types import AssistantMessage, Message, Usage

# ---------------------------------------------------------------------------
# Stop reason
# ---------------------------------------------------------------------------


class StopReason(enum.StrEnum):
    """Why the agent loop terminated."""

    END_TURN = "end_turn"
    MAX_TURNS = "max_turns"
    MAX_BUDGET = "max_budget"
    ABORTED = "aborted"


# ---------------------------------------------------------------------------
# Agent result
# ---------------------------------------------------------------------------


@dataclass
class AgentResult:
    """Final output of an agent run."""

    messages: list[Message]
    final_message: AssistantMessage
    total_usage: Usage
    turn_count: int
    stop_reason: StopReason


# ---------------------------------------------------------------------------
# Agent events — discriminated union
# ---------------------------------------------------------------------------


@dataclass
class TurnStartEvent:
    """Emitted when a new turn begins."""

    turn: int
    type: str = "turn_start"


@dataclass
class ToolExecutingEvent:
    """Emitted when a tool call starts executing."""

    tool_use_id: str
    name: str
    input: Any
    type: str = "tool_executing"


@dataclass
class ToolCompleteEvent:
    """Emitted when a tool call finishes."""

    tool_use_id: str
    name: str
    result: Any
    error: Exception | None = None
    type: str = "tool_complete"


@dataclass
class ContextCompactedEvent:
    """Emitted when the context was compacted to fit token limits."""

    old_tokens: int
    new_tokens: int
    type: str = "context_compacted"


@dataclass
class TurnCompleteEvent:
    """Emitted at the end of a turn."""

    turn: int
    message: AssistantMessage
    usage: Usage
    type: str = "turn_complete"


@dataclass
class CompleteEvent:
    """Emitted when the agent loop finishes."""

    result: AgentResult
    type: str = "complete"


AgentEvent = (
    TurnStartEvent
    | ToolExecutingEvent
    | ToolCompleteEvent
    | ContextCompactedEvent
    | TurnCompleteEvent
    | CompleteEvent
)


# ---------------------------------------------------------------------------
# Context strategies
# ---------------------------------------------------------------------------


class ContextExceededError(Exception):
    """Raised when the context window is exceeded and no recovery is possible."""


class ContextStrategy(Protocol):
    """Strategy for compacting messages when context is exceeded."""

    def compact(self, messages: list[Message], max_tokens: int) -> list[Message]: ...


class FailStrategy:
    """Context strategy that raises on overflow."""

    def compact(self, messages: list[Message], max_tokens: int) -> list[Message]:
        raise ContextExceededError(f"context exceeded {max_tokens} tokens")


@dataclass
class TruncateStrategy:
    """Context strategy that keeps only the last N messages."""

    keep_last: int = 10

    def compact(self, messages: list[Message], max_tokens: int) -> list[Message]:
        if len(messages) > self.keep_last:
            return messages[-self.keep_last :]
        return messages

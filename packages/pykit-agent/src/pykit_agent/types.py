"""Agent result, budget exceptions, and context strategies."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Protocol

from pykit_ai import StreamEvent, Usage
from pykit_llm.types import AssistantMessage, Message


class StopReason(enum.StrEnum):
    """Why the agent loop terminated."""

    END_TURN = "stop"  # aligns with FinishReason.STOP
    MAX_TURNS = "max_turns"
    MAX_TOKENS = "length"  # aligns with FinishReason.LENGTH
    MAX_TOOL_CALLS = "max_tool_calls"
    WALL_CLOCK = "wall_clock"
    CANCELLED = "cancelled"
    ERROR = "error"


class AgentBudgetError(Exception):
    """Base class for typed agent budget failures."""


class WallClockExceededError(AgentBudgetError):
    """Wall-clock budget was exceeded."""


class MaxToolCallsExceededError(AgentBudgetError):
    """Tool-call budget was exceeded."""


class MaxTokensExceededError(AgentBudgetError):
    """Token budget was exceeded."""


class MaxTurnsExceededError(AgentBudgetError):
    """Turn budget was exceeded."""


class HookError(Exception):
    """A hook failed."""


@dataclass
class AgentResult:
    """Final output of an agent run."""

    messages: list[Message]
    final_message: AssistantMessage
    total_usage: Usage
    turn_count: int
    stop_reason: StopReason


AgentEvent = StreamEvent


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

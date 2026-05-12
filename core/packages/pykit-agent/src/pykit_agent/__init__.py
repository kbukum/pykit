"""pykit-agent — bounded agent loop with canonical hooks and stream events."""

from pykit_agent.agent import Agent, AgentConfig
from pykit_agent.command import Command, CommandRegistry, register_builtins
from pykit_agent.hooks import (
    EVENT_ON_ERROR,
    EVENT_ON_LLM_REQUEST,
    EVENT_ON_LLM_RESPONSE,
    EVENT_ON_MCP_REQUEST,
    EVENT_ON_MCP_RESULT,
    EVENT_ON_START,
    EVENT_ON_STEP_COMPLETE,
    EVENT_ON_STOP,
    EVENT_ON_TOOL_CALL,
    EVENT_ON_TOOL_RESULT,
)
from pykit_agent.memory import InMemoryStore, Memory, SlidingWindowMemory
from pykit_agent.types import (
    AgentBudgetError,
    AgentEvent,
    AgentResult,
    ContextExceededError,
    ContextStrategy,
    FailStrategy,
    HookError,
    MaxTokensExceededError,
    MaxToolCallsExceededError,
    MaxTurnsExceededError,
    StopReason,
    TruncateStrategy,
    WallClockExceededError,
)
from pykit_hook import Registry as HookRegistry

__all__ = [
    "Agent",
    "AgentBudgetError",
    "AgentConfig",
    "AgentEvent",
    "AgentResult",
    "Command",
    "CommandRegistry",
    "ContextExceededError",
    "ContextStrategy",
    "FailStrategy",
    "EVENT_ON_ERROR",
    "EVENT_ON_LLM_REQUEST",
    "EVENT_ON_LLM_RESPONSE",
    "EVENT_ON_MCP_REQUEST",
    "EVENT_ON_MCP_RESULT",
    "EVENT_ON_START",
    "EVENT_ON_STEP_COMPLETE",
    "EVENT_ON_STOP",
    "EVENT_ON_TOOL_CALL",
    "EVENT_ON_TOOL_RESULT",
    "HookError",
    "HookRegistry",
    "InMemoryStore",
    "MaxTokensExceededError",
    "MaxToolCallsExceededError",
    "MaxTurnsExceededError",
    "Memory",
    "SlidingWindowMemory",
    "StopReason",
    "TruncateStrategy",
    "WallClockExceededError",
    "register_builtins",
]

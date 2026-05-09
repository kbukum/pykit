"""pykit-agent — bounded agent loop with canonical hooks and stream events."""

from pykit_agent.agent import Agent, AgentConfig
from pykit_agent.command import Command, CommandRegistry, register_builtins
from pykit_agent.hooks import AgentHook, NoopHook
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

__all__ = [
    "Agent",
    "AgentBudgetError",
    "AgentConfig",
    "AgentEvent",
    "AgentHook",
    "AgentResult",
    "Command",
    "CommandRegistry",
    "ContextExceededError",
    "ContextStrategy",
    "FailStrategy",
    "HookError",
    "InMemoryStore",
    "MaxTokensExceededError",
    "MaxToolCallsExceededError",
    "MaxTurnsExceededError",
    "Memory",
    "NoopHook",
    "SlidingWindowMemory",
    "StopReason",
    "TruncateStrategy",
    "WallClockExceededError",
    "register_builtins",
]

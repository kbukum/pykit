"""Canonical agent hook events emitted through ``pykit_hook.Registry``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pykit_ai import ToolResultBlock
from pykit_hook import EventType
from pykit_llm.types import AssistantMessage, CompletionRequest, CompletionResponse

EVENT_ON_START: EventType = "on_start"
EVENT_ON_LLM_REQUEST: EventType = "on_llm_request"
EVENT_ON_LLM_RESPONSE: EventType = "on_llm_response"
EVENT_ON_TOOL_CALL: EventType = "on_tool_call"
EVENT_ON_TOOL_RESULT: EventType = "on_tool_result"
EVENT_ON_MCP_REQUEST: EventType = "on_mcp_request"
EVENT_ON_MCP_RESULT: EventType = "on_mcp_result"
EVENT_ON_STEP_COMPLETE: EventType = "on_step_complete"
EVENT_ON_ERROR: EventType = "on_error"
EVENT_ON_STOP: EventType = "on_stop"


@dataclass(frozen=True)
class StartEvent:
    """Event emitted when a turn starts."""

    turn: int
    type: EventType = EVENT_ON_START


@dataclass(frozen=True)
class LLMRequestEvent:
    """Event emitted before sending a completion request."""

    request: CompletionRequest
    type: EventType = EVENT_ON_LLM_REQUEST


@dataclass(frozen=True)
class LLMResponseEvent:
    """Event emitted after receiving a completion response."""

    response: CompletionResponse
    type: EventType = EVENT_ON_LLM_RESPONSE


@dataclass(frozen=True)
class ToolCallEvent:
    """Event emitted before executing a tool call."""

    name: str
    input_data: dict[str, object]
    type: EventType = EVENT_ON_TOOL_CALL


@dataclass(frozen=True)
class ToolResultEvent:
    """Event emitted after a tool call completes."""

    name: str
    result: ToolResultBlock
    type: EventType = EVENT_ON_TOOL_RESULT


@dataclass(frozen=True)
class MCPRequestEvent:
    """Event emitted before dispatching an MCP request."""

    server: str
    method: str
    input_data: dict[str, object]
    type: EventType = EVENT_ON_MCP_REQUEST


@dataclass(frozen=True)
class MCPResultEvent:
    """Event emitted after receiving an MCP response."""

    server: str
    method: str
    result: Any
    type: EventType = EVENT_ON_MCP_RESULT


@dataclass(frozen=True)
class StepCompleteEvent:
    """Event emitted after a turn finishes."""

    turn: int
    message: AssistantMessage
    type: EventType = EVENT_ON_STEP_COMPLETE


@dataclass(frozen=True)
class ErrorEvent:
    """Event emitted when agent execution raises an error."""

    error: Exception
    type: EventType = EVENT_ON_ERROR


@dataclass(frozen=True)
class StopEvent:
    """Event emitted when the agent loop stops."""

    reason: str
    type: EventType = EVENT_ON_STOP

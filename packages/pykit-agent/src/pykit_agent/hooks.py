"""Canonical observe-only agent hook Protocol."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pykit_ai import ToolResultBlock
from pykit_llm.types import AssistantMessage, CompletionRequest
from pykit_llm.types import CompletionResponse as LLMResponse


@runtime_checkable
class AgentHook(Protocol):
    """Observe-only async hook surface for the agent loop."""

    async def on_start(self, turn: int) -> None:
        """Observe the start of an agent turn."""

    async def on_llm_request(self, request: CompletionRequest) -> None:
        """Observe an outbound LLM request."""

    async def on_llm_response(self, response: LLMResponse) -> None:
        """Observe an inbound LLM response."""

    async def on_tool_call(self, name: str, input_data: dict[str, object]) -> None:
        """Observe a tool invocation before execution."""

    async def on_tool_result(self, name: str, result: ToolResultBlock) -> None:
        """Observe the result produced by a tool invocation."""

    async def on_mcp_request(self, server: str, method: str, input_data: dict[str, object]) -> None:
        """Observe an outbound MCP request."""

    async def on_mcp_result(self, server: str, method: str, result: Any) -> None:
        """Observe the result returned by an MCP server."""

    # MCP server result payloads are intentionally opaque at this layer.

    async def on_step_complete(self, turn: int, message: AssistantMessage) -> None:
        """Observe completion of a turn with its final assistant message."""

    async def on_error(self, error: Exception) -> None:
        """Observe an error raised during agent execution."""

    async def on_stop(self, reason: str) -> None:
        """Observe the reason the agent loop stopped."""


class NoopHook:
    """Default hook implementation."""

    async def on_start(self, turn: int) -> None:
        return None

    async def on_llm_request(self, request: CompletionRequest) -> None:
        return None

    async def on_llm_response(self, response: LLMResponse) -> None:
        return None

    async def on_tool_call(self, name: str, input_data: dict[str, object]) -> None:
        return None

    async def on_tool_result(self, name: str, result: ToolResultBlock) -> None:
        return None

    async def on_mcp_request(self, server: str, method: str, input_data: dict[str, object]) -> None:
        return None

    async def on_mcp_result(self, server: str, method: str, result: Any) -> None:
        return None

    async def on_step_complete(self, turn: int, message: AssistantMessage) -> None:
        return None

    async def on_error(self, error: Exception) -> None:
        return None

    async def on_stop(self, reason: str) -> None:
        return None

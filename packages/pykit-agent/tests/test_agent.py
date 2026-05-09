from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

import pytest

from pykit_agent import Agent, AgentConfig, StopReason
from pykit_ai import ToolResultBlock, ToolUseBlock
from pykit_llm.provider import Capabilities
from pykit_llm.stream_events import MessageStart, MessageStop, StreamEvent, TextDelta, UsageDelta
from pykit_llm.types import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    Message,
    TextBlock,
    Usage,
    user,
)
from pykit_schema import ValidationResult
from pykit_tool import Context, Definition, Registry, Result


class MockProvider:
    def __init__(self, responses: list[CompletionResponse]) -> None:
        self.responses = responses
        self.requests: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        return self.responses.pop(0)

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamEvent]:
        yield TextDelta(text="mock")

    def capabilities(self) -> Capabilities:
        return Capabilities()

    def count_tokens(self, messages: list[Message]) -> int:
        return 1


class RecordingHook:
    def __init__(self) -> None:
        self.events: list[str] = []

    async def on_start(self, turn: int) -> None:
        self.events.append("on_start")

    async def on_llm_request(self, request: CompletionRequest) -> None:
        self.events.append("on_llm_request")

    async def on_llm_response(self, response: CompletionResponse) -> None:
        self.events.append("on_llm_response")

    async def on_tool_call(self, name: str, input_data: dict[str, object]) -> None:
        self.events.append("on_tool_call")

    async def on_tool_result(self, name: str, result: ToolResultBlock) -> None:
        self.events.append("on_tool_result")

    async def on_mcp_request(self, server: str, method: str, input_data: dict[str, object]) -> None:
        self.events.append("on_mcp_request")

    async def on_mcp_result(self, server: str, method: str, result: object) -> None:
        self.events.append("on_mcp_result")

    async def on_step_complete(self, turn: int, message: AssistantMessage) -> None:
        self.events.append("on_step_complete")

    async def on_error(self, error: Exception) -> None:
        self.events.append("on_error")

    async def on_stop(self, reason: str) -> None:
        self.events.append("on_stop")


class EchoMCPTool:
    @property
    def definition(self) -> Definition:
        return Definition(name="echo", description="Echo text")

    @property
    def mcp_server(self) -> str:
        return "test-server"

    @property
    def mcp_method(self) -> str:
        return "tools/call"

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True)

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        return Result(content=str(input_data["text"]))


def response(text: str, usage: Usage | None = None) -> CompletionResponse:
    return CompletionResponse(
        message=AssistantMessage(content=[TextBlock(text=text)]),
        model="mock",
        usage=usage or Usage(input_tokens=1, output_tokens=1),
    )


def tool_call_response() -> CompletionResponse:
    return CompletionResponse(
        message=AssistantMessage(tool_calls=[ToolUseBlock(id="call-1", name="echo", input={"text": "ok"})]),
        model="mock",
        usage=Usage(input_tokens=1, output_tokens=1),
    )


def test_config_defaults() -> None:
    provider = MockProvider([response("ok")])
    cfg = AgentConfig(provider=provider)
    assert cfg.max_turns == 10
    assert cfg.max_tokens == 100_000
    assert cfg.wall_clock_seconds == 60.0
    assert cfg.max_tool_calls == 50
    assert cfg.tool_concurrency == 4
    assert cfg.tool_timeout_seconds == 30.0


@pytest.mark.asyncio
async def test_stream_surfaces_llm_events_and_hooks() -> None:
    hook = RecordingHook()
    provider = MockProvider([response("ok")])
    agent = Agent(AgentConfig(provider=provider, hooks=(hook,)))
    events = [event async for event in agent.stream([user("hi")])]
    assert [type(event) for event in events] == [MessageStart, UsageDelta, MessageStop]
    assert "on_start" in hook.events
    assert "on_llm_request" in hook.events
    assert "on_llm_response" in hook.events
    assert "on_step_complete" in hook.events
    assert "on_stop" in hook.events


@pytest.mark.asyncio
async def test_complete_tool_turn_fires_canonical_hook_events() -> None:
    hook = RecordingHook()
    provider = MockProvider([tool_call_response(), response("done")])
    tools = Registry()
    tools.register(EchoMCPTool())

    result = await Agent(AgentConfig(provider=provider, tools=tools, hooks=(hook,))).run([user("hi")])

    assert result.stop_reason is StopReason.END_TURN
    assert hook.events == [
        "on_start",
        "on_llm_request",
        "on_llm_response",
        "on_tool_call",
        "on_mcp_request",
        "on_tool_result",
        "on_mcp_result",
        "on_step_complete",
        "on_start",
        "on_llm_request",
        "on_llm_response",
        "on_step_complete",
        "on_stop",
    ]


@pytest.mark.asyncio
async def test_run_returns_result() -> None:
    provider = MockProvider([response("ok")])
    result = await Agent(AgentConfig(provider=provider)).run([user("hi")])
    assert result.stop_reason is StopReason.END_TURN


@pytest.mark.asyncio
async def test_token_budget_terminal_error() -> None:
    provider = MockProvider([response("too much", Usage(input_tokens=5))])
    agent = Agent(AgentConfig(provider=provider, max_tokens=1))
    events = [event async for event in agent.stream([user("hi")])]
    assert events[-1].type == "stream.error"


@pytest.mark.asyncio
async def test_zero_budgets_are_runtime_budget_errors() -> None:
    provider = MockProvider([response("unused")])
    token_events = [
        event async for event in Agent(AgentConfig(provider=provider, max_tokens=0)).stream([user("hi")])
    ]
    assert token_events[-1].type == "stream.error"
    assert token_events[-1].code == "MaxTokensExceededError"

    turn_events = [
        event async for event in Agent(AgentConfig(provider=provider, max_turns=0)).stream([user("hi")])
    ]
    assert turn_events[-1].type == "stream.error"
    assert turn_events[-1].code == "MaxTurnsExceededError"


@pytest.mark.asyncio
async def test_cancellation_propagates_promptly() -> None:
    class SlowProvider(MockProvider):
        async def complete(self, request: CompletionRequest) -> CompletionResponse:
            await asyncio.sleep(5)
            return response("late")

    agent = Agent(AgentConfig(provider=SlowProvider([])))
    task = asyncio.create_task(_drain(agent))
    await asyncio.sleep(0.01)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(task, timeout=1.0)


async def _drain(agent: Agent) -> None:
    async for _event in agent.stream([user("hi")]):
        pass

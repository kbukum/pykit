"""Tests for pykit-agent module."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest

from pykit_agent.agent import Agent, AgentConfig
from pykit_agent.types import (
    AgentResult,
    ContextCompactedEvent,
    ContextExceededError,
    FailStrategy,
    StopReason,
    ToolCompleteEvent,
    ToolExecutingEvent,
    TruncateStrategy,
    TurnStartEvent,
)
from pykit_hook.registry import HookRegistry
from pykit_hook.types import Action, EventType, HookEvent, HookResult, PreLLMCall
from pykit_llm.provider import Capabilities
from pykit_llm.stream_events import ContentDelta, StreamEvent
from pykit_llm.types import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    FunctionCall,
    Message,
    TextBlock,
    ToolCall,
    Usage,
    user,
)
from pykit_tool import Context, Registry, tool

# ---------------------------------------------------------------------------
# Mock Provider
# ---------------------------------------------------------------------------


class MockProvider:
    """A mock Provider that returns pre-configured responses."""

    def __init__(self, responses: list[CompletionResponse], caps: Capabilities | None = None) -> None:
        self._responses = list(responses)
        self._call_index = 0
        self._caps = caps or Capabilities(model_id="mock")
        self.requests: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        if self._call_index >= len(self._responses):
            raise RuntimeError("no more mock responses")
        resp = self._responses[self._call_index]
        self._call_index += 1
        return resp

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamEvent]:
        yield ContentDelta(text="mock")

    def capabilities(self) -> Capabilities:
        return self._caps

    def count_tokens(self, messages: list[Message]) -> int:
        return 10


def _text_response(text: str, usage: Usage | None = None) -> CompletionResponse:
    """Build a simple text completion response."""
    return CompletionResponse(
        message=AssistantMessage(content=[TextBlock(text=text)]),
        model="mock",
        usage=usage or Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


def _tool_call_response(
    tool_id: str, name: str, arguments: dict[str, Any], usage: Usage | None = None
) -> CompletionResponse:
    """Build a response with a tool call."""
    return CompletionResponse(
        message=AssistantMessage(
            tool_calls=[
                ToolCall(id=tool_id, function=FunctionCall(name=name, arguments=json.dumps(arguments)))
            ]
        ),
        model="mock",
        usage=usage or Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
    )


# ---------------------------------------------------------------------------
# Type tests
# ---------------------------------------------------------------------------


class TestStopReason:
    """StopReason enum."""

    def test_values(self) -> None:
        assert StopReason.END_TURN.value == "end_turn"
        assert StopReason.MAX_TURNS.value == "max_turns"
        assert StopReason.MAX_BUDGET.value == "max_budget"
        assert StopReason.ABORTED.value == "aborted"


class TestAgentResult:
    """AgentResult dataclass."""

    def test_construction(self) -> None:
        msg = AssistantMessage(content=[TextBlock(text="done")])
        r = AgentResult(
            messages=[],
            final_message=msg,
            total_usage=Usage(total_tokens=100),
            turn_count=3,
            stop_reason=StopReason.END_TURN,
        )
        assert r.turn_count == 3
        assert r.stop_reason == StopReason.END_TURN
        assert r.final_message is msg


class TestContextStrategies:
    """ContextStrategy implementations."""

    def test_fail_strategy_raises(self) -> None:
        s = FailStrategy()
        with pytest.raises(ContextExceededError):
            s.compact([], 100)

    def test_truncate_strategy_keeps_last(self) -> None:
        msgs: list[Message] = [user(f"msg{i}") for i in range(10)]
        s = TruncateStrategy(keep_last=3)
        result = s.compact(msgs, 100)
        assert len(result) == 3

    def test_truncate_strategy_no_truncation_needed(self) -> None:
        msgs: list[Message] = [user("a"), user("b")]
        s = TruncateStrategy(keep_last=5)
        result = s.compact(msgs, 100)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Agent loop tests
# ---------------------------------------------------------------------------


class TestAgentRun:
    """Agent.run() integration tests."""

    @pytest.mark.asyncio
    async def test_simple_completion(self) -> None:
        provider = MockProvider([_text_response("Hello!")])
        agent = Agent(AgentConfig(provider=provider))
        result = await agent.run([user("Hi")])
        assert result.stop_reason == StopReason.END_TURN
        assert result.turn_count == 1
        assert result.total_usage.total_tokens == 15

    @pytest.mark.asyncio
    async def test_with_system_prompt(self) -> None:
        provider = MockProvider([_text_response("response")])
        agent = Agent(AgentConfig(provider=provider, system_prompt="You are helpful"))
        await agent.run([user("Hi")])
        req = provider.requests[0]
        # System prompt should be prepended
        assert any(
            hasattr(m, "content") and isinstance(m.content, str) and m.content == "You are helpful"
            for m in req.messages
        )

    @pytest.mark.asyncio
    async def test_tool_call_and_response(self) -> None:
        @tool(description="Add two numbers")
        async def add(ctx: Context, a: int, b: int) -> int:
            return a + b

        registry = Registry()
        registry.register(add)

        provider = MockProvider([
            _tool_call_response("tc1", "add", {"a": 2, "b": 3}),
            _text_response("The sum is 5"),
        ])
        agent = Agent(AgentConfig(provider=provider, tools=registry))
        result = await agent.run([user("What is 2+3?")])
        assert result.stop_reason == StopReason.END_TURN
        assert result.turn_count == 2

    @pytest.mark.asyncio
    async def test_max_turns(self) -> None:
        # Provider always returns tool calls — should stop at max_turns
        responses = [_tool_call_response(f"tc{i}", "echo", {"text": "x"}) for i in range(5)]

        @tool(description="Echo")
        async def echo(ctx: Context, text: str) -> str:
            return text

        registry = Registry()
        registry.register(echo)

        provider = MockProvider(responses)
        agent = Agent(AgentConfig(provider=provider, tools=registry, max_turns=3))
        result = await agent.run([user("loop")])
        assert result.stop_reason == StopReason.MAX_TURNS
        assert result.turn_count == 3

    @pytest.mark.asyncio
    async def test_max_budget(self) -> None:
        big_usage = Usage(prompt_tokens=500, completion_tokens=500, total_tokens=1000)
        provider = MockProvider([
            _tool_call_response("tc1", "echo", {"text": "x"}, usage=big_usage),
            _text_response("done"),
        ])

        @tool(description="Echo")
        async def echo(ctx: Context, text: str) -> str:
            return text

        registry = Registry()
        registry.register(echo)

        agent = Agent(AgentConfig(provider=provider, tools=registry, max_token_budget=500))
        result = await agent.run([user("run")])
        assert result.stop_reason == StopReason.MAX_BUDGET

    @pytest.mark.asyncio
    async def test_no_tools_registry(self) -> None:
        # Provider returns a tool call but agent has no tool registry
        provider = MockProvider([
            _tool_call_response("tc1", "search", {"q": "test"}),
            _text_response("Sorry, no tools"),
        ])
        agent = Agent(AgentConfig(provider=provider))
        result = await agent.run([user("search")])
        assert result.stop_reason == StopReason.END_TURN


class TestAgentStream:
    """Agent.stream() event emission."""

    @pytest.mark.asyncio
    async def test_emits_turn_start_and_complete(self) -> None:
        provider = MockProvider([_text_response("Hi")])
        agent = Agent(AgentConfig(provider=provider))
        events = [e async for e in agent.stream([user("Hi")])]
        types = [type(e).__name__ for e in events]
        assert "TurnStartEvent" in types
        assert "TurnCompleteEvent" in types
        assert "CompleteEvent" in types

    @pytest.mark.asyncio
    async def test_emits_tool_events(self) -> None:
        @tool(description="Echo")
        async def echo(ctx: Context, text: str) -> str:
            return text

        registry = Registry()
        registry.register(echo)

        provider = MockProvider([
            _tool_call_response("tc1", "echo", {"text": "hello"}),
            _text_response("echoed"),
        ])
        agent = Agent(AgentConfig(provider=provider, tools=registry))
        events = [e async for e in agent.stream([user("echo hello")])]
        types = [type(e).__name__ for e in events]
        assert "ToolExecutingEvent" in types
        assert "ToolCompleteEvent" in types

    @pytest.mark.asyncio
    async def test_emits_context_compacted_event(self) -> None:
        # Use a context strategy and provider with small max_context_tokens
        caps = Capabilities(model_id="mock", max_context_tokens=10)
        provider = MockProvider(
            [
                _tool_call_response("tc1", "echo", {"text": "x" * 100}),
                _text_response("done"),
            ],
            caps=caps,
        )

        @tool(description="Echo")
        async def echo(ctx: Context, text: str) -> str:
            return text

        registry = Registry()
        registry.register(echo)

        agent = Agent(
            AgentConfig(
                provider=provider,
                tools=registry,
                context_strategy=TruncateStrategy(keep_last=2),
            )
        )
        events = [e async for e in agent.stream([user("test")])]
        types = [type(e).__name__ for e in events]
        assert "ContextCompactedEvent" in types


class TestAgentHooks:
    """Agent hook integration."""

    @pytest.mark.asyncio
    async def test_turn_start_hook_called(self) -> None:
        called: list[int] = []
        hooks = HookRegistry()
        hooks.on(EventType.TURN_START, lambda e: (called.append(1), HookResult())[1])

        provider = MockProvider([_text_response("ok")])
        agent = Agent(AgentConfig(provider=provider, hooks=hooks))
        await agent.run([user("Hi")])
        assert len(called) == 1

    @pytest.mark.asyncio
    async def test_abort_on_turn_start(self) -> None:
        hooks = HookRegistry()
        hooks.on(
            EventType.TURN_START,
            lambda e: HookResult(action=Action.ABORT, reason="nope"),
        )

        provider = MockProvider([_text_response("never")])
        agent = Agent(AgentConfig(provider=provider, hooks=hooks))
        result = await agent.run([user("Hi")])
        assert result.stop_reason == StopReason.ABORTED

    @pytest.mark.asyncio
    async def test_pre_llm_modify_hook(self) -> None:
        def modify_request(event: HookEvent) -> HookResult:
            if isinstance(event, PreLLMCall):
                modified = CompletionRequest(
                    messages=event.request.messages,
                    temperature=0.0,
                )
                return HookResult(action=Action.MODIFY, modified_data=modified)
            return HookResult()

        hooks = HookRegistry()
        hooks.on(EventType.PRE_LLM_CALL, modify_request)

        provider = MockProvider([_text_response("ok")])
        agent = Agent(AgentConfig(provider=provider, hooks=hooks))
        await agent.run([user("Hi")])
        # The modified request should have temperature=0.0
        assert provider.requests[0].temperature == 0.0

    @pytest.mark.asyncio
    async def test_tool_hooks_called(self) -> None:
        pre_calls: list[str] = []
        post_calls: list[str] = []

        hooks = HookRegistry()
        hooks.on(EventType.PRE_TOOL_CALL, lambda e: (pre_calls.append(e.name), HookResult())[1])
        hooks.on(EventType.POST_TOOL_CALL, lambda e: (post_calls.append(e.name), HookResult())[1])

        @tool(description="Echo")
        async def echo(ctx: Context, text: str) -> str:
            return text

        registry = Registry()
        registry.register(echo)

        provider = MockProvider([
            _tool_call_response("tc1", "echo", {"text": "hello"}),
            _text_response("done"),
        ])
        agent = Agent(AgentConfig(provider=provider, tools=registry, hooks=hooks))
        await agent.run([user("echo")])
        assert "echo" in pre_calls
        assert "echo" in post_calls

    @pytest.mark.asyncio
    async def test_abort_pre_tool_call(self) -> None:
        hooks = HookRegistry()
        hooks.on(
            EventType.PRE_TOOL_CALL,
            lambda e: HookResult(action=Action.ABORT, reason="blocked"),
        )

        @tool(description="Echo")
        async def echo(ctx: Context, text: str) -> str:
            return text

        registry = Registry()
        registry.register(echo)

        provider = MockProvider([
            _tool_call_response("tc1", "echo", {"text": "hello"}),
            _text_response("done"),
        ])
        agent = Agent(AgentConfig(provider=provider, tools=registry, hooks=hooks))
        result = await agent.run([user("echo")])
        # Should still complete since abort only skips the tool call
        assert result.stop_reason == StopReason.END_TURN


class TestAgentEventTypes:
    """Agent event type construction."""

    def test_turn_start_event(self) -> None:
        e = TurnStartEvent(turn=1)
        assert e.turn == 1
        assert e.type == "turn_start"

    def test_tool_executing_event(self) -> None:
        e = ToolExecutingEvent(tool_use_id="t1", name="search", input={"q": "test"})
        assert e.name == "search"
        assert e.type == "tool_executing"

    def test_tool_complete_event(self) -> None:
        e = ToolCompleteEvent(tool_use_id="t1", name="search", result="found")
        assert e.result == "found"
        assert e.error is None
        assert e.type == "tool_complete"

    def test_context_compacted_event(self) -> None:
        e = ContextCompactedEvent(old_tokens=1000, new_tokens=500)
        assert e.old_tokens == 1000
        assert e.type == "context_compacted"

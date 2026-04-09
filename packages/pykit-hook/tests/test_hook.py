"""Tests for pykit-hook module."""

from __future__ import annotations

from pykit_hook.registry import HookRegistry
from pykit_hook.types import (
    Action,
    EventType,
    HookEvent,
    HookResult,
    OnError,
    PostLLMCall,
    PostToolCall,
    PreLLMCall,
    PreToolCall,
    TurnEnd,
    TurnStart,
)
from pykit_llm.types import AssistantMessage, CompletionRequest, CompletionResponse


class TestEventTypes:
    """HookEvent variant construction."""

    def test_pre_tool_call(self) -> None:
        e = PreToolCall(type=EventType.PRE_TOOL_CALL, name="search", input={"q": "test"})
        assert e.type == EventType.PRE_TOOL_CALL
        assert e.name == "search"
        assert e.input == {"q": "test"}

    def test_post_tool_call(self) -> None:
        e = PostToolCall(
            type=EventType.POST_TOOL_CALL,
            name="search",
            input={"q": "test"},
            result="found",
            error=None,
        )
        assert e.result == "found"
        assert e.error is None

    def test_post_tool_call_with_error(self) -> None:
        err = RuntimeError("fail")
        e = PostToolCall(
            type=EventType.POST_TOOL_CALL,
            name="search",
            input={},
            error=err,
        )
        assert e.error is err

    def test_pre_llm_call(self) -> None:
        req = CompletionRequest(messages=[])
        e = PreLLMCall(type=EventType.PRE_LLM_CALL, request=req)
        assert e.request is req

    def test_post_llm_call(self) -> None:
        resp = CompletionResponse(message=AssistantMessage())
        e = PostLLMCall(type=EventType.POST_LLM_CALL, response=resp)
        assert e.response is resp
        assert e.error is None

    def test_on_error(self) -> None:
        err = ValueError("bad input")
        e = OnError(type=EventType.ON_ERROR, error=err, source="tool:search")
        assert e.error is err
        assert e.source == "tool:search"

    def test_turn_start(self) -> None:
        e = TurnStart(type=EventType.TURN_START, turn=1)
        assert e.turn == 1

    def test_turn_end(self) -> None:
        msg = AssistantMessage()
        e = TurnEnd(type=EventType.TURN_END, turn=1, message=msg)
        assert e.turn == 1
        assert e.message is msg


class TestAction:
    """Action enum values."""

    def test_values(self) -> None:
        assert Action.CONTINUE.value == "continue"
        assert Action.ABORT.value == "abort"
        assert Action.MODIFY.value == "modify"


class TestHookResult:
    """HookResult defaults and construction."""

    def test_defaults(self) -> None:
        r = HookResult()
        assert r.action == Action.CONTINUE
        assert r.modified_data is None
        assert r.reason == ""

    def test_abort(self) -> None:
        r = HookResult(action=Action.ABORT, reason="cancelled by user")
        assert r.action == Action.ABORT
        assert r.reason == "cancelled by user"

    def test_modify(self) -> None:
        r = HookResult(action=Action.MODIFY, modified_data={"key": "value"})
        assert r.action == Action.MODIFY
        assert r.modified_data == {"key": "value"}


class TestHookRegistry:
    """HookRegistry subscribe / emit."""

    def test_emit_no_handlers(self) -> None:
        reg = HookRegistry()
        result = reg.emit(TurnStart(type=EventType.TURN_START, turn=1))
        assert result.action == Action.CONTINUE

    def test_handler_called(self) -> None:
        calls: list[HookEvent] = []

        def handler(event: HookEvent) -> HookResult:
            calls.append(event)
            return HookResult()

        reg = HookRegistry()
        reg.on(EventType.TURN_START, handler)
        reg.emit(TurnStart(type=EventType.TURN_START, turn=1))
        assert len(calls) == 1
        assert isinstance(calls[0], TurnStart)

    def test_multiple_handlers_sequential(self) -> None:
        order: list[str] = []

        def first(event: HookEvent) -> HookResult:
            order.append("first")
            return HookResult()

        def second(event: HookEvent) -> HookResult:
            order.append("second")
            return HookResult()

        reg = HookRegistry()
        reg.on(EventType.PRE_TOOL_CALL, first)
        reg.on(EventType.PRE_TOOL_CALL, second)
        reg.emit(PreToolCall(type=EventType.PRE_TOOL_CALL, name="test"))
        assert order == ["first", "second"]

    def test_abort_short_circuits(self) -> None:
        order: list[str] = []

        def aborter(event: HookEvent) -> HookResult:
            order.append("aborter")
            return HookResult(action=Action.ABORT, reason="stop")

        def after_abort(event: HookEvent) -> HookResult:
            order.append("after_abort")
            return HookResult()

        reg = HookRegistry()
        reg.on(EventType.PRE_TOOL_CALL, aborter)
        reg.on(EventType.PRE_TOOL_CALL, after_abort)
        result = reg.emit(PreToolCall(type=EventType.PRE_TOOL_CALL, name="test"))
        assert result.action == Action.ABORT
        assert result.reason == "stop"
        assert order == ["aborter"]

    def test_modify_chains(self) -> None:
        def first_mod(event: HookEvent) -> HookResult:
            return HookResult(action=Action.MODIFY, modified_data={"step": 1})

        def second_mod(event: HookEvent) -> HookResult:
            return HookResult(action=Action.MODIFY, modified_data={"step": 2})

        reg = HookRegistry()
        reg.on(EventType.PRE_LLM_CALL, first_mod)
        reg.on(EventType.PRE_LLM_CALL, second_mod)
        result = reg.emit(PreLLMCall(type=EventType.PRE_LLM_CALL))
        assert result.action == Action.MODIFY
        assert result.modified_data == {"step": 2}

    def test_unsubscribe(self) -> None:
        calls: list[int] = []

        def handler(event: HookEvent) -> HookResult:
            calls.append(1)
            return HookResult()

        reg = HookRegistry()
        unsub = reg.on(EventType.TURN_END, handler)
        reg.emit(TurnEnd(type=EventType.TURN_END))
        assert len(calls) == 1

        unsub()
        reg.emit(TurnEnd(type=EventType.TURN_END))
        assert len(calls) == 1  # not called again

    def test_unsubscribe_idempotent(self) -> None:
        reg = HookRegistry()
        unsub = reg.on(EventType.TURN_START, lambda e: HookResult())
        unsub()
        unsub()  # should not raise

    def test_has_handlers(self) -> None:
        reg = HookRegistry()
        assert reg.has_handlers(EventType.PRE_TOOL_CALL) is False
        reg.on(EventType.PRE_TOOL_CALL, lambda e: HookResult())
        assert reg.has_handlers(EventType.PRE_TOOL_CALL) is True

    def test_clear_specific(self) -> None:
        reg = HookRegistry()
        reg.on(EventType.PRE_TOOL_CALL, lambda e: HookResult())
        reg.on(EventType.POST_TOOL_CALL, lambda e: HookResult())
        reg.clear(EventType.PRE_TOOL_CALL)
        assert reg.has_handlers(EventType.PRE_TOOL_CALL) is False
        assert reg.has_handlers(EventType.POST_TOOL_CALL) is True

    def test_clear_all(self) -> None:
        reg = HookRegistry()
        reg.on(EventType.PRE_TOOL_CALL, lambda e: HookResult())
        reg.on(EventType.POST_TOOL_CALL, lambda e: HookResult())
        reg.clear()
        assert reg.has_handlers(EventType.PRE_TOOL_CALL) is False
        assert reg.has_handlers(EventType.POST_TOOL_CALL) is False

    def test_different_event_types_isolated(self) -> None:
        pre_calls: list[int] = []
        post_calls: list[int] = []

        reg = HookRegistry()
        reg.on(EventType.PRE_TOOL_CALL, lambda e: (pre_calls.append(1), HookResult())[1])
        reg.on(EventType.POST_TOOL_CALL, lambda e: (post_calls.append(1), HookResult())[1])

        reg.emit(PreToolCall(type=EventType.PRE_TOOL_CALL, name="test"))
        assert len(pre_calls) == 1
        assert len(post_calls) == 0

"""Tests for tool calling types in pykit_llm."""

from __future__ import annotations

from pykit_llm import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    FunctionCall,
    StreamChunk,
    TextBlock,
    ToolCall,
    ToolChoice,
    ToolResultMessage,
    UserMessage,
    assistant,
    text_of,
    tool_result_msg,
    user,
)


class TestToolCall:
    def test_basic(self):
        tc = ToolCall(
            id="call_abc",
            function=FunctionCall(name="search", arguments='{"q":"test"}'),
        )
        assert tc.id == "call_abc"
        assert tc.type == "function"
        assert tc.function.name == "search"
        assert tc.function.arguments == '{"q":"test"}'

    def test_custom_type(self):
        tc = ToolCall(id="1", function=FunctionCall(name="f", arguments="{}"), type="custom")
        assert tc.type == "custom"


class TestToolResultMessage:
    def test_basic(self):
        result = ToolResultMessage(tool_use_id="call_1", content="42")
        assert result.is_error is False

    def test_error(self):
        result = ToolResultMessage(tool_use_id="call_1", content="not found", is_error=True)
        assert result.is_error is True

    def test_role(self):
        result = ToolResultMessage(tool_use_id="call_1", content="result data")
        assert result.role == "tool_result"
        assert result.content == "result data"
        assert result.tool_use_id == "call_1"

    def test_convenience_constructor(self):
        msg = tool_result_msg("call_1", "result data")
        assert msg.role == "tool_result"
        assert msg.content == "result data"
        assert msg.tool_use_id == "call_1"
        assert msg.is_error is False

    def test_convenience_constructor_error(self):
        msg = tool_result_msg("call_1", "error msg", is_error=True)
        assert msg.is_error is True


class TestToolChoice:
    def test_auto(self):
        tc = ToolChoice.auto()
        assert tc.mode == "auto"
        assert tc.function is None

    def test_none(self):
        tc = ToolChoice.none()
        assert tc.mode == "none"

    def test_required(self):
        tc = ToolChoice.required()
        assert tc.mode == "required"

    def test_specific(self):
        tc = ToolChoice.specific("get_weather")
        assert tc.mode == "specific"
        assert tc.function == "get_weather"


class TestMessageWithTools:
    def test_assistant_tool_calls(self):
        msg = AssistantMessage(
            content=[TextBlock(text="")],
            tool_calls=[
                ToolCall(id="1", function=FunctionCall(name="search", arguments='{"q":"test"}')),
                ToolCall(id="2", function=FunctionCall(name="fetch", arguments='{"url":"x"}')),
            ],
        )
        assert len(msg.tool_calls) == 2
        assert msg.tool_calls[0].function.name == "search"

    def test_tool_result_message(self):
        msg = ToolResultMessage(tool_use_id="call_1", content="result")
        assert msg.tool_use_id == "call_1"
        assert msg.role == "tool_result"

    def test_user_message_defaults(self):
        msg = user("hello")
        assert isinstance(msg, UserMessage)
        assert msg.role == "user"
        assert text_of(msg.content) == "hello"

    def test_assistant_defaults(self):
        msg = assistant("hi")
        assert msg.tool_calls == []


class TestCompletionRequestWithTools:
    def test_tools_field(self):
        req = CompletionRequest(
            messages=[user("hello")],
            tool_choice=ToolChoice.auto(),
        )
        assert req.tools is None
        assert req.tool_choice.mode == "auto"

    def test_defaults(self):
        req = CompletionRequest(messages=[])
        assert req.tools is None
        assert req.tool_choice is None


class TestCompletionResponseWithTools:
    def test_has_tool_calls_false(self):
        resp = CompletionResponse(message=assistant("hello"))
        assert resp.has_tool_calls() is False

    def test_has_tool_calls_empty(self):
        resp = CompletionResponse(message=AssistantMessage(tool_calls=[]))
        assert resp.has_tool_calls() is False

    def test_has_tool_calls_true(self):
        resp = CompletionResponse(
            message=AssistantMessage(
                tool_calls=[
                    ToolCall(id="1", function=FunctionCall(name="f", arguments="{}")),
                ],
            ),
        )
        assert resp.has_tool_calls() is True

    def test_stop_reason_tool_use(self):
        resp = CompletionResponse(message=assistant(""), stop_reason="tool_use")
        assert resp.stop_reason == "tool_use"


class TestStreamChunkWithTools:
    def test_tool_calls_field(self):
        chunk = StreamChunk(
            tool_calls=[
                ToolCall(id="1", function=FunctionCall(name="f", arguments="{}")),
            ]
        )
        assert len(chunk.tool_calls) == 1

    def test_defaults(self):
        chunk = StreamChunk()
        assert chunk.tool_calls is None

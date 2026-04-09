"""Tests for StreamEvent discriminated union types."""

from __future__ import annotations

from pykit_llm.stream_events import (
    ContentDelta,
    MessageComplete,
    MessageStart,
    StreamError,
    StreamEvent,
    ThinkingDelta,
    ToolCallDelta,
    UsageUpdate,
)
from pykit_llm.types import AssistantMessage, CompletionResponse, Usage


class TestStreamEventTypes:
    """StreamEvent variant construction and discriminator."""

    def test_content_delta(self) -> None:
        e = ContentDelta(text="hello")
        assert e.text == "hello"
        assert e.type == "content_delta"

    def test_tool_call_delta(self) -> None:
        e = ToolCallDelta(tool_use_id="t1", name="search", arguments_chunk='{"q":')
        assert e.tool_use_id == "t1"
        assert e.name == "search"
        assert e.arguments_chunk == '{"q":'
        assert e.type == "tool_call_delta"

    def test_tool_call_delta_name_none(self) -> None:
        e = ToolCallDelta(tool_use_id="t1", name=None, arguments_chunk='"v"}')
        assert e.name is None

    def test_thinking_delta(self) -> None:
        e = ThinkingDelta(text="reasoning")
        assert e.text == "reasoning"
        assert e.type == "thinking_delta"

    def test_usage_update(self) -> None:
        u = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        e = UsageUpdate(usage=u)
        assert e.usage.total_tokens == 15
        assert e.type == "usage_update"

    def test_message_start(self) -> None:
        e = MessageStart(model="gpt-4", role="assistant")
        assert e.model == "gpt-4"
        assert e.role == "assistant"
        assert e.type == "message_start"

    def test_message_complete(self) -> None:
        resp = CompletionResponse(
            message=AssistantMessage(),
            model="gpt-4",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )
        e = MessageComplete(response=resp)
        assert e.response.model == "gpt-4"
        assert e.type == "message_complete"

    def test_stream_error(self) -> None:
        e = StreamError(error="connection lost", code="CONN_ERR")
        assert e.error == "connection lost"
        assert e.code == "CONN_ERR"
        assert e.type == "stream_error"

    def test_stream_error_no_code(self) -> None:
        e = StreamError(error="unknown")
        assert e.code is None


class TestStreamEventUnion:
    """StreamEvent union type checks."""

    def test_all_variants_match_union(self) -> None:
        u = Usage()
        resp = CompletionResponse(message=AssistantMessage())
        events: list[StreamEvent] = [
            ContentDelta(text="a"),
            ToolCallDelta(tool_use_id="t", name="n", arguments_chunk="c"),
            ThinkingDelta(text="t"),
            UsageUpdate(usage=u),
            MessageStart(model="m", role="r"),
            MessageComplete(response=resp),
            StreamError(error="e"),
        ]
        assert len(events) == 7

    def test_discriminator_field_uniqueness(self) -> None:
        types = {
            ContentDelta(text="").type,
            ToolCallDelta(tool_use_id="", name=None, arguments_chunk="").type,
            ThinkingDelta(text="").type,
            UsageUpdate(usage=Usage()).type,
            MessageStart(model="", role="").type,
            MessageComplete(response=CompletionResponse(message=AssistantMessage())).type,
            StreamError(error="").type,
        }
        assert len(types) == 7, "All discriminators must be unique"

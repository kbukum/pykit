from __future__ import annotations

from pykit_llm.stream_events import (
    Error,
    MessageStart,
    MessageStop,
    ReasoningDelta,
    StreamEvent,
    TextDelta,
    ToolUseDelta,
    UsageDelta,
)
from pykit_llm.types import AssistantMessage, CompletionResponse, Usage


def test_stream_event_variants_have_canonical_wire_names() -> None:
    response = CompletionResponse(message=AssistantMessage())
    events: list[StreamEvent] = [
        MessageStart(model="m", role="assistant"),
        TextDelta(text="hi"),
        ToolUseDelta(id="t", input_delta="{}"),
        ReasoningDelta(text="because"),
        UsageDelta(usage=Usage(input_tokens=1), cached_tokens=2),
        MessageStop(response=response),
        Error(error="boom"),
    ]
    assert [event.type for event in events] == [
        "message.start",
        "text.delta",
        "tool_use.delta",
        "reasoning.delta",
        "usage.delta",
        "message.stop",
        "stream.error",
    ]
    assert isinstance(events[4], UsageDelta)
    assert events[4].cached_tokens == 2

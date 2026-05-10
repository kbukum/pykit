from __future__ import annotations

import pytest
from pydantic import TypeAdapter, ValidationError

from pykit_ai import (
    AnyStreamEvent,
    Error,
    FinishReason,
    MessageStart,
    MessageStop,
    ReasoningDelta,
    TextDelta,
    ToolUseDelta,
    ToolUseStart,
    ToolUseStop,
    Usage,
    UsageDelta,
    semconv,
)
from pykit_ai.semconv import Operation


def test_semconv_key_set_and_operation_values_are_canonical() -> None:
    keys = {
        value
        for name, value in vars(semconv).items()
        if name.startswith("GENAI_") and isinstance(value, str) and value.startswith("gen_ai.")
    }
    assert keys == {
        "gen_ai.system",
        "gen_ai.operation.name",
        "gen_ai.request.id",
        "gen_ai.request.model",
        "gen_ai.request.model.version",
        "gen_ai.request.max_tokens",
        "gen_ai.request.temperature",
        "gen_ai.response.model",
        "gen_ai.response.finish_reason",
        "gen_ai.tool.name",
        "gen_ai.usage.input_tokens",
        "gen_ai.usage.output_tokens",
        "gen_ai.usage.cached_tokens",
        "gen_ai.usage.reasoning_tokens",
    }
    assert {operation.value for operation in Operation} == {
        "agent.run",
        "agent.turn",
        "chat",
        "embedding",
        "inference.request",
        "llm.call",
        "mcp.request",
        "stream",
        "text_completion",
        "tool.call",
    }
    assert all(not operation.value.startswith("gen_ai.") for operation in Operation)


def test_stream_event_variant_set_is_canonical() -> None:
    variants = AnyStreamEvent.__value__.__args__[0].__args__
    assert {variant.__name__ for variant in variants} == {
        "MessageStart",
        "TextDelta",
        "ReasoningDelta",
        "ToolUseStart",
        "ToolUseDelta",
        "ToolUseStop",
        "MessageStop",
        "UsageDelta",
        "StreamError",
    }


def test_stream_event_discriminator_accepts_canonical_events() -> None:
    adapter = TypeAdapter(AnyStreamEvent)
    events = [
        adapter.validate_python({"type": "message.start", "model": "m", "role": "assistant"}),
        adapter.validate_python({"type": "text.delta", "text": "hi"}),
        adapter.validate_python({"type": "reasoning.delta", "text": "why"}),
        adapter.validate_python({"type": "tool_use.start", "id": "t1", "name": "search"}),
        adapter.validate_python({"type": "tool_use.delta", "id": "t1", "input_delta": "{}"}),
        adapter.validate_python({"type": "tool_use.stop", "id": "t1"}),
        adapter.validate_python({"type": "message.stop", "finish_reason": "cancelled"}),
        adapter.validate_python({"type": "usage.delta", "usage": {"input_tokens": 1}}),
        adapter.validate_python({"type": "stream.error", "error": "boom"}),
    ]
    assert [type(event) for event in events] == [
        MessageStart,
        TextDelta,
        ReasoningDelta,
        ToolUseStart,
        ToolUseDelta,
        ToolUseStop,
        MessageStop,
        UsageDelta,
        Error,
    ]
    assert events[6].finish_reason is FinishReason.CANCELLED


def test_stream_event_rejects_removed_cancelled_variant() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(AnyStreamEvent).validate_python({"type": "cancelled"})


def test_usage_rejects_legacy_token_aliases() -> None:
    with pytest.raises(ValidationError):
        Usage(prompt_tokens=1)

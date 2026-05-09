from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import TypeAdapter, ValidationError

from pykit_ai import (
    AnyStreamEvent,
    Budget,
    BudgetExceeded,
    BudgetExceededReason,
    Capabilities,
    ContentPart,
    Cost,
    FinishReason,
    MessageStart,
    Model,
    Provider,
    RateLimited,
    Role,
    StreamEvent,
    TextBlock,
    TextDelta,
    ToolResultBlock,
    ToolUseBlock,
    Usage,
    semconv,
)


def test_content_part_discriminator_parses_all_core_blocks() -> None:
    adapter = TypeAdapter(ContentPart)

    text = adapter.validate_python({"type": "text", "text": "hello"})
    tool_use = adapter.validate_python(
        {"type": "tool_use", "id": "u1", "name": "lookup", "input": {"q": "x"}}
    )
    tool_result = adapter.validate_python(
        {"type": "tool_result", "id": "u1", "content": ["ok"], "is_error": False}
    )

    assert isinstance(text, TextBlock)
    assert isinstance(tool_use, ToolUseBlock)
    assert isinstance(tool_result, ToolResultBlock)
    assert tool_result.id == "u1"
    assert tool_result.content == ["ok"]


def test_content_part_rejects_unknown_variant() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(ContentPart).validate_python({"type": "unknown", "text": "nope"})


def test_model_capabilities_provider_and_roles() -> None:
    caps = Capabilities(streaming=True, tool_use=True, max_input_tokens=128)
    model = Model(name="gpt-test", provider=Provider.OPENAI, version="2025", capabilities=caps)

    assert model.provider == Provider.OPENAI
    assert model.capabilities.streaming is True
    assert model.capabilities.tool_use is True
    assert model.capabilities.max_input_tokens == 128
    assert Role.ASSISTANT.value == "assistant"


def test_usage_exposes_normative_names() -> None:
    usage = Usage(input_tokens=10, output_tokens=3, cached_tokens=2, reasoning_tokens=1)

    assert usage.input_tokens == 10
    assert usage.output_tokens == 3
    assert usage.cached_tokens == 2
    assert usage.reasoning_tokens == 1


def test_cost_budget_and_budget_exception_reason() -> None:
    budget = Budget(max_tokens=100, max_calls=2, max_cost=Cost(input=Decimal("0.01")), wall_clock=5.0)
    exc = BudgetExceeded(BudgetExceededReason.TOKENS)

    assert budget.max_cost is not None
    assert budget.max_cost.input == Decimal("0.01")
    assert exc.reason is BudgetExceededReason.TOKENS
    assert "tokens" in str(exc)


def test_stream_event_discriminator_and_aliases() -> None:
    adapter = TypeAdapter(AnyStreamEvent)
    start = adapter.validate_python({"type": "message.start", "model": "m", "role": "assistant"})
    delta = adapter.validate_python({"type": "text.delta", "text": "hi"})

    assert isinstance(start, MessageStart)
    assert isinstance(delta, TextDelta)
    assert isinstance(start, StreamEvent)
    assert isinstance(delta, StreamEvent)
    assert FinishReason.TOOL_USE.value == "tool_use"


def test_typed_error_hierarchy_and_semconv_keys() -> None:
    assert isinstance(RateLimited("slow down"), Exception)
    assert f"gen_{'ai'}.system" == semconv.GENAI_SYSTEM
    assert f"gen_{'ai'}.usage.reasoning_tokens" == semconv.GENAI_USAGE_REASONING_TOKENS

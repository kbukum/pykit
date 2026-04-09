"""Tests for the explain module."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

import pytest

from pykit_explain import Explanation, ReasoningStep, Request, Signal, generate
from pykit_explain.explain import _extract_json, _render_prompt, _render_signal_table
from pykit_llm.types import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    StreamChunk,
    TextBlock,
    Usage,
)

# ---------------------------------------------------------------------------
# Mock provider
# ---------------------------------------------------------------------------


class MockLLMProvider:
    """A mock LLM provider that returns a fixed response."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text
        self.last_request: CompletionRequest | None = None

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.last_request = request
        return CompletionResponse(
            message=AssistantMessage(content=[TextBlock(text=self._response_text)]),
            model="mock",
            usage=Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
            stop_reason="end_turn",
        )

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        yield StreamChunk(content=self._response_text, done=True)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class TestTypes:
    def test_signal(self):
        s = Signal(name="sentiment", value=0.85, label="positive")
        assert s.name == "sentiment"
        assert s.value == 0.85
        assert s.label == "positive"

    def test_reasoning_step(self):
        step = ReasoningStep(signal="sentiment", finding="high score", impact="positive tone")
        assert step.signal == "sentiment"
        assert step.finding == "high score"
        assert step.impact == "positive tone"

    def test_request_defaults(self):
        req = Request(signals=[])
        assert req.signals == []
        assert req.template is None
        assert req.max_tokens is None
        assert req.context is None

    def test_explanation_defaults(self):
        exp = Explanation(summary="test")
        assert exp.summary == "test"
        assert exp.reasoning == []
        assert exp.key_factors == []
        assert exp.confidence == 0.0


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class TestRenderHelpers:
    def test_render_signal_table(self):
        signals = [
            Signal(name="sentiment", value=0.85, label="positive"),
            Signal(name="engagement", value=0.72, label="moderate"),
        ]
        table = _render_signal_table(signals)
        assert "sentiment" in table
        assert "0.8500" in table
        assert "engagement" in table
        assert "0.7200" in table

    def test_render_prompt_default_template(self):
        req = Request(
            signals=[Signal(name="score", value=0.9, label="high")],
        )
        prompt = _render_prompt(req)
        assert "score" in prompt
        assert "0.9000" in prompt
        assert "JSON" in prompt

    def test_render_prompt_with_context(self):
        req = Request(
            signals=[Signal(name="score", value=0.9, label="high")],
            context="This is about a video analysis",
        )
        prompt = _render_prompt(req)
        assert "This is about a video analysis" in prompt

    def test_render_prompt_custom_template(self):
        req = Request(
            signals=[Signal(name="score", value=0.9, label="high")],
            template="Signals:\n{signal_table}\n{context_section}Done.",
        )
        prompt = _render_prompt(req)
        assert "Signals:" in prompt
        assert "score" in prompt
        assert "Done." in prompt


class TestExtractJson:
    def test_plain_json(self):
        data = _extract_json('{"summary": "test"}')
        assert data["summary"] == "test"

    def test_fenced_json(self):
        text = '```json\n{"summary": "test"}\n```'
        data = _extract_json(text)
        assert data["summary"] == "test"

    def test_fenced_without_language(self):
        text = '```\n{"summary": "test"}\n```'
        data = _extract_json(text)
        assert data["summary"] == "test"

    def test_surrounded_fenced(self):
        text = 'Here is the result:\n```json\n{"summary": "test"}\n```\nDone.'
        data = _extract_json(text)
        assert data["summary"] == "test"

    def test_invalid_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _extract_json("not json")


# ---------------------------------------------------------------------------
# Generate function
# ---------------------------------------------------------------------------


class TestGenerate:
    async def test_generate_basic(self):
        response_json = json.dumps(
            {
                "summary": "The content shows strong positive sentiment.",
                "reasoning": [
                    {
                        "signal": "sentiment",
                        "finding": "Score of 0.85 indicates positive tone",
                        "impact": "Content is well-received",
                    },
                ],
                "key_factors": ["positive sentiment", "high engagement"],
                "confidence": 0.9,
            }
        )
        provider = MockLLMProvider(response_json)
        request = Request(
            signals=[
                Signal(name="sentiment", value=0.85, label="positive"),
                Signal(name="engagement", value=0.72, label="moderate"),
            ],
        )
        result = await generate(provider, request)

        assert isinstance(result, Explanation)
        assert "positive sentiment" in result.summary.lower() or result.summary != ""
        assert len(result.reasoning) == 1
        assert result.reasoning[0].signal == "sentiment"
        assert len(result.key_factors) == 2
        assert result.confidence == 0.9

    async def test_generate_with_fenced_response(self):
        inner = json.dumps(
            {
                "summary": "Test summary",
                "reasoning": [],
                "key_factors": [],
                "confidence": 0.5,
            }
        )
        response_text = f"```json\n{inner}\n```"
        provider = MockLLMProvider(response_text)
        request = Request(
            signals=[Signal(name="test", value=1.0, label="high")],
        )
        result = await generate(provider, request)
        assert result.summary == "Test summary"
        assert result.confidence == 0.5

    async def test_generate_passes_max_tokens(self):
        response_json = json.dumps(
            {
                "summary": "ok",
                "reasoning": [],
                "key_factors": [],
                "confidence": 0.5,
            }
        )
        provider = MockLLMProvider(response_json)
        request = Request(
            signals=[Signal(name="test", value=1.0, label="high")],
            max_tokens=512,
        )
        await generate(provider, request)
        assert provider.last_request is not None
        assert provider.last_request.max_tokens == 512

    async def test_generate_uses_low_temperature(self):
        response_json = json.dumps(
            {
                "summary": "ok",
                "reasoning": [],
                "key_factors": [],
                "confidence": 0.5,
            }
        )
        provider = MockLLMProvider(response_json)
        request = Request(
            signals=[Signal(name="test", value=1.0, label="high")],
        )
        await generate(provider, request)
        assert provider.last_request is not None
        assert provider.last_request.temperature == 0.3

    async def test_generate_with_context(self):
        response_json = json.dumps(
            {
                "summary": "ok",
                "reasoning": [],
                "key_factors": [],
                "confidence": 0.5,
            }
        )
        provider = MockLLMProvider(response_json)
        request = Request(
            signals=[Signal(name="test", value=1.0, label="high")],
            context="Video analysis context",
        )
        await generate(provider, request)
        assert provider.last_request is not None
        msg_content = provider.last_request.messages[0]
        # Verify context appears in the prompt
        from pykit_llm.types import text_of

        prompt_text = text_of(msg_content.content)  # type: ignore[arg-type]
        assert "Video analysis context" in prompt_text

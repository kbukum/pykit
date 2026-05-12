"""Tests for StructuredOutput and ParseError."""

from __future__ import annotations

import json

import pytest
from pydantic import BaseModel

from pykit_llm.structured import ParseError, StructuredOutput
from pykit_llm.types import AssistantMessage, CompletionResponse, TextBlock, Usage

# ---------------------------------------------------------------------------
# Test models
# ---------------------------------------------------------------------------


class Sentiment(BaseModel):
    label: str
    score: float


class Address(BaseModel):
    street: str
    city: str
    zip_code: str


# ---------------------------------------------------------------------------
# StructuredOutput — parse
# ---------------------------------------------------------------------------


class TestStructuredOutputParse:
    def test_parse_plain_json(self) -> None:
        so: StructuredOutput[Sentiment] = StructuredOutput(Sentiment)
        result = so.parse('{"label": "positive", "score": 0.95}')
        assert result.label == "positive"
        assert result.score == 0.95

    def test_parse_json_code_block(self) -> None:
        so: StructuredOutput[Sentiment] = StructuredOutput(Sentiment)
        text = '```json\n{"label": "negative", "score": 0.1}\n```'
        result = so.parse(text)
        assert result.label == "negative"
        assert result.score == 0.1

    def test_parse_code_block_without_language(self) -> None:
        so: StructuredOutput[Sentiment] = StructuredOutput(Sentiment)
        text = '```\n{"label": "neutral", "score": 0.5}\n```'
        result = so.parse(text)
        assert result.label == "neutral"

    def test_parse_with_surrounding_text(self) -> None:
        so: StructuredOutput[Sentiment] = StructuredOutput(Sentiment)
        text = 'Here is the result:\n```json\n{"label": "positive", "score": 0.9}\n```\nDone.'
        result = so.parse(text)
        assert result.label == "positive"

    def test_parse_invalid_json_raises_parse_error(self) -> None:
        so: StructuredOutput[Sentiment] = StructuredOutput(Sentiment)
        with pytest.raises(ParseError, match="Invalid JSON"):
            so.parse("not json at all")

    def test_parse_validation_failure_raises_parse_error(self) -> None:
        so: StructuredOutput[Sentiment] = StructuredOutput(Sentiment)
        with pytest.raises(ParseError, match="Validation failed"):
            so.parse('{"label": "ok"}')  # missing score

    def test_parse_error_contains_raw_text(self) -> None:
        so: StructuredOutput[Sentiment] = StructuredOutput(Sentiment)
        raw = "bad data"
        with pytest.raises(ParseError) as exc_info:
            so.parse(raw)
        assert exc_info.value.raw_text == raw


# ---------------------------------------------------------------------------
# StructuredOutput — parse_from_response
# ---------------------------------------------------------------------------


class TestStructuredOutputParseFromResponse:
    def test_parse_from_response(self) -> None:
        so: StructuredOutput[Address] = StructuredOutput(Address)
        data = json.dumps({"street": "123 Main", "city": "NYC", "zip_code": "10001"})
        msg = AssistantMessage(content=[TextBlock(text=data)])
        resp = CompletionResponse(message=msg, model="test", usage=Usage())
        result = so.parse_from_response(resp)
        assert result.city == "NYC"

    def test_parse_from_response_no_text_raises(self) -> None:
        so: StructuredOutput[Sentiment] = StructuredOutput(Sentiment)
        msg = AssistantMessage(content=[])
        resp = CompletionResponse(message=msg, model="test", usage=Usage())
        with pytest.raises(ParseError, match="No text content"):
            so.parse_from_response(resp)

    def test_parse_from_response_multiple_text_blocks(self) -> None:
        so: StructuredOutput[Sentiment] = StructuredOutput(Sentiment)
        msg = AssistantMessage(
            content=[
                TextBlock(text='{"label": "pos"'),
                TextBlock(text=', "score": 0.8}'),
            ]
        )
        resp = CompletionResponse(message=msg, model="test", usage=Usage())
        result = so.parse_from_response(resp)
        assert result.label == "pos"
        assert result.score == 0.8


# ---------------------------------------------------------------------------
# StructuredOutput — system_instruction
# ---------------------------------------------------------------------------


class TestStructuredOutputSystemInstruction:
    def test_system_instruction_contains_schema(self) -> None:
        so: StructuredOutput[Sentiment] = StructuredOutput(Sentiment)
        instruction = so.system_instruction()
        assert "json" in instruction.lower()
        assert "label" in instruction
        assert "score" in instruction

    def test_system_instruction_valid_json_schema(self) -> None:
        so: StructuredOutput[Address] = StructuredOutput(Address)
        instruction = so.system_instruction()
        # Extract the JSON block
        start = instruction.index("```json\n") + len("```json\n")
        end = instruction.index("\n```", start)
        schema = json.loads(instruction[start:end])
        assert "properties" in schema


# ---------------------------------------------------------------------------
# ParseError
# ---------------------------------------------------------------------------


class TestParseError:
    def test_message_and_raw_text(self) -> None:
        err = ParseError("bad", raw_text="raw")
        assert str(err) == "bad"
        assert err.raw_text == "raw"

    def test_default_raw_text(self) -> None:
        err = ParseError("oops")
        assert err.raw_text == ""

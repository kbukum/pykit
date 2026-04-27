"""Explanation generation using LLM providers."""

from __future__ import annotations

import json
import re
from typing import Any, cast

from pykit_explain.types import Explanation, ReasoningStep, Request, Signal
from pykit_llm.provider import LLMProvider
from pykit_llm.types import CompletionRequest, user

_DEFAULT_TEMPLATE = """\
You are an expert analyst. Given the following analysis signals, produce a structured \
explanation in JSON format.

## Signals

{signal_table}

{context_section}\
Respond with a JSON object containing:
- "summary": A concise summary explanation (1-2 sentences)
- "reasoning": An array of objects, each with "signal", "finding", and "impact" fields
- "key_factors": An array of the most important factors (strings)
- "confidence": A float between 0.0 and 1.0 indicating overall confidence

Respond ONLY with the JSON object, no other text."""


def _render_signal_table(signals: list[Signal]) -> str:
    """Render signals as a markdown table."""
    lines = ["| Signal | Value | Label |", "|--------|-------|-------|"]
    for s in signals:
        lines.append(f"| {s.name} | {s.value:.4f} | {s.label} |")
    return "\n".join(lines)


def _render_prompt(request: Request) -> str:
    """Render the full prompt from a request."""
    template = request.template or _DEFAULT_TEMPLATE
    signal_table = _render_signal_table(request.signals)
    context_section = f"## Context\n\n{request.context}\n\n" if request.context else ""
    return template.format(signal_table=signal_table, context_section=context_section)


def _extract_json(text: str) -> dict[str, Any]:
    """Extract JSON from LLM response, handling markdown fencing."""
    text = text.strip()
    # Try to extract from markdown code fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if match:
        text = match.group(1).strip()
    return cast("dict[str, Any]", json.loads(text))


def _parse_explanation(data: dict[str, Any]) -> Explanation:
    """Parse a JSON dict into an Explanation dataclass."""
    reasoning = [
        ReasoningStep(
            signal=step.get("signal", ""),
            finding=step.get("finding", ""),
            impact=step.get("impact", ""),
        )
        for step in data.get("reasoning", [])
    ]
    return Explanation(
        summary=data.get("summary", ""),
        reasoning=reasoning,
        key_factors=data.get("key_factors", []),
        confidence=float(data.get("confidence", 0.0)),
    )


async def generate(provider: LLMProvider, request: Request) -> Explanation:
    """Generate a structured explanation from analysis signals.

    Args:
        provider: An LLM provider implementing the LLMProvider protocol.
        request: The explanation request containing signals and optional template.

    Returns:
        A structured Explanation with summary, reasoning, key factors, and confidence.
    """
    prompt = _render_prompt(request)
    completion_request = CompletionRequest(
        messages=[user(prompt)],
        temperature=0.3,
        max_tokens=request.max_tokens,
    )
    response = await provider.complete(completion_request)
    text = response.text()
    data = _extract_json(text)
    return _parse_explanation(data)

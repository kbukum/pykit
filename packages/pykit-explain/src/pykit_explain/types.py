"""Explain module types — signals, requests, and structured explanations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Signal:
    """A single analysis signal with a name, numeric value, and descriptive label."""

    name: str
    value: float
    label: str


@dataclass
class ReasoningStep:
    """One step in the explanation reasoning chain."""

    signal: str
    finding: str
    impact: str


@dataclass
class Request:
    """A request to generate an explanation from analysis signals."""

    signals: list[Signal]
    template: str | None = None
    max_tokens: int | None = None
    context: str | None = None


@dataclass
class Explanation:
    """A structured explanation generated from analysis signals."""

    summary: str
    reasoning: list[ReasoningStep] = field(default_factory=list)
    key_factors: list[str] = field(default_factory=list)
    confidence: float = 0.0

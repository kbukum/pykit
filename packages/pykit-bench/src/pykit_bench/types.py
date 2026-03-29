"""Core data types for the bench framework.

These types mirror gokit's bench core types, adapted with Python idioms.
Uses Generic[L] for type-safe label handling and dataclasses for lightweight structs.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

L = TypeVar("L")


@dataclass
class BenchSample[L]:
    """A labeled data point in an evaluation dataset.

    Generic over label type ``L`` for type-safe label handling.
    """

    id: str
    """Unique sample identifier."""

    label: L
    """Ground-truth label."""

    input: bytes = b""
    """Raw input data (file contents)."""

    source: str = ""
    """Optional source reference."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional metadata."""


@dataclass
class Prediction[L]:
    """An evaluator's output for a single sample."""

    label: L
    """Predicted label."""

    score: float = 0.0
    """Primary confidence score (typically 0.0-1.0)."""

    sample_id: str = ""
    """Reference back to the sample."""

    scores: dict[str, float] = field(default_factory=dict)
    """Per-label scores (for multi-class)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Additional prediction metadata."""


@dataclass
class ScoredSample[L]:
    """Pairs ground-truth sample with its prediction for metric computation."""

    sample: BenchSample[L]
    prediction: Prediction[L]


# Type alias for label mapping functions.
LabelMapper = Callable[[str], L]
"""Converts string labels from a manifest into typed labels."""


def string_label_mapper(s: str) -> str:
    """String-passthrough label mapper for simple string-labeled datasets."""
    return s

"""Embedding data types, distance metrics, and aggregation functions."""

from __future__ import annotations

import math
from dataclasses import dataclass, field


@dataclass
class Embedding:
    """An embedding vector with optional metadata."""

    vector: list[float]
    text: str | None = None
    model: str | None = None

    @property
    def dims(self) -> int:
        """Return the dimensionality of this embedding."""
        return len(self.vector)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute the cosine similarity between two vectors.

    Returns a value in [-1.0, 1.0] where 1.0 means identical direction.
    Returns 0.0 if either vector has zero magnitude.
    """
    if len(a) != len(b):
        raise ValueError("vectors must have equal dimensions")

    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return dot / (norm_a * norm_b)


def euclidean_distance(a: list[float], b: list[float]) -> float:
    """Compute the Euclidean (L2) distance between two vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must have equal dimensions")

    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def dot_product(a: list[float], b: list[float]) -> float:
    """Compute the dot product of two vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must have equal dimensions")

    return sum(x * y for x, y in zip(a, b, strict=True))


def mean_pooling(vectors: list[list[float]]) -> list[float] | None:
    """Compute the element-wise mean of a collection of vectors.

    Returns None if the input is empty.
    """
    if not vectors:
        return None

    dims = len(vectors[0])
    count = len(vectors)
    result = [0.0] * dims

    for v in vectors:
        if len(v) != dims:
            raise ValueError("all vectors must have equal dimensions")
        for i, val in enumerate(v):
            result[i] += val

    return [x / count for x in result]


def max_pooling(vectors: list[list[float]]) -> list[float] | None:
    """Compute the element-wise maximum of a collection of vectors.

    Returns None if the input is empty.
    """
    if not vectors:
        return None

    dims = len(vectors[0])
    result = [float("-inf")] * dims

    for v in vectors:
        if len(v) != dims:
            raise ValueError("all vectors must have equal dimensions")
        for i, val in enumerate(v):
            if val > result[i]:
                result[i] = val

    return result

"""Vector math helpers shared by AI modules."""

from __future__ import annotations

import math


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute the cosine similarity between two vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must have equal dimensions")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def euclidean_distance(a: list[float], b: list[float]) -> float:
    """Compute the Euclidean distance between two vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must have equal dimensions")
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b, strict=True)))


def dot_product(a: list[float], b: list[float]) -> float:
    """Compute the dot product of two vectors."""
    if len(a) != len(b):
        raise ValueError("vectors must have equal dimensions")
    return sum(x * y for x, y in zip(a, b, strict=True))


def mean_pooling(vectors: list[list[float]]) -> list[float] | None:
    """Compute the element-wise mean of a collection of vectors."""
    if not vectors:
        return None
    dims = len(vectors[0])
    result = [0.0] * dims
    for vector in vectors:
        if len(vector) != dims:
            raise ValueError("all vectors must have equal dimensions")
        for index, value in enumerate(vector):
            result[index] += value
    return [value / len(vectors) for value in result]


def max_pooling(vectors: list[list[float]]) -> list[float] | None:
    """Compute the element-wise maximum of a collection of vectors."""
    if not vectors:
        return None
    dims = len(vectors[0])
    result = [float("-inf")] * dims
    for vector in vectors:
        if len(vector) != dims:
            raise ValueError("all vectors must have equal dimensions")
        for index, value in enumerate(vector):
            result[index] = max(result[index], value)
    return result


def normalize(vector: list[float]) -> list[float]:
    """Return an L2-normalized vector."""
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return [0.0 for _ in vector]
    return [value / norm for value in vector]


__all__ = [
    "cosine_similarity",
    "dot_product",
    "euclidean_distance",
    "max_pooling",
    "mean_pooling",
    "normalize",
]

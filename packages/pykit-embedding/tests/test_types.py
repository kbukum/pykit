"""Tests for embedding types, distance metrics, and aggregation functions."""

from __future__ import annotations

import math

import pytest

from pykit_embedding.types import (
    Embedding,
    cosine_similarity,
    dot_product,
    euclidean_distance,
    max_pooling,
    mean_pooling,
)


class TestEmbedding:
    def test_new(self) -> None:
        e = Embedding(vector=[1.0, 2.0, 3.0])
        assert e.dims == 3
        assert e.text is None
        assert e.model is None

    def test_with_metadata(self) -> None:
        e = Embedding(vector=[1.0, 2.0], text="hello", model="test-model")
        assert e.dims == 2
        assert e.text == "hello"
        assert e.model == "test-model"


class TestCosineSimilarity:
    def test_identical_vectors(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(cosine_similarity(a, b)) < 1e-6

    def test_zero_vector(self) -> None:
        a = [1.0, 2.0]
        zero = [0.0, 0.0]
        assert cosine_similarity(a, zero) == 0.0

    def test_opposite_vectors(self) -> None:
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(cosine_similarity(a, b) - (-1.0)) < 1e-6

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="equal dimensions"):
            cosine_similarity([1.0, 2.0], [1.0])


class TestEuclideanDistance:
    def test_same_point(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert abs(euclidean_distance(v, v)) < 1e-6

    def test_known_value(self) -> None:
        a = [0.0, 0.0]
        b = [3.0, 4.0]
        assert abs(euclidean_distance(a, b) - 5.0) < 1e-6

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="equal dimensions"):
            euclidean_distance([1.0], [1.0, 2.0])


class TestDotProduct:
    def test_known_value(self) -> None:
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        assert abs(dot_product(a, b) - 32.0) < 1e-6

    def test_orthogonal(self) -> None:
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(dot_product(a, b)) < 1e-6

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="equal dimensions"):
            dot_product([1.0], [1.0, 2.0])


class TestMeanPooling:
    def test_empty(self) -> None:
        assert mean_pooling([]) is None

    def test_single(self) -> None:
        result = mean_pooling([[2.0, 4.0]])
        assert result is not None
        assert abs(result[0] - 2.0) < 1e-6
        assert abs(result[1] - 4.0) < 1e-6

    def test_multiple(self) -> None:
        result = mean_pooling([[1.0, 3.0], [3.0, 1.0]])
        assert result is not None
        assert abs(result[0] - 2.0) < 1e-6
        assert abs(result[1] - 2.0) < 1e-6

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="equal dimensions"):
            mean_pooling([[1.0, 2.0], [1.0]])


class TestMaxPooling:
    def test_empty(self) -> None:
        assert max_pooling([]) is None

    def test_selects_max(self) -> None:
        result = max_pooling([[1.0, 4.0], [3.0, 2.0]])
        assert result is not None
        assert abs(result[0] - 3.0) < 1e-6
        assert abs(result[1] - 4.0) < 1e-6

    def test_single(self) -> None:
        result = max_pooling([[5.0, 10.0]])
        assert result is not None
        assert abs(result[0] - 5.0) < 1e-6
        assert abs(result[1] - 10.0) < 1e-6

    def test_dimension_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="equal dimensions"):
            max_pooling([[1.0, 2.0], [1.0]])

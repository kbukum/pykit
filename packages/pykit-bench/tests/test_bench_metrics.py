"""Tests for pykit.bench.metrics module."""

from __future__ import annotations

import pytest

from pykit_bench.metrics import (
    compute_metrics,
    per_branch_metrics,
    threshold_sweep,
)


class TestComputeMetrics:
    def test_perfect_classification(self) -> None:
        scores = [0.9, 0.8, 0.1, 0.2]
        labels = [True, True, False, False]
        m = compute_metrics(scores, labels, 0.5)
        assert m.precision == 1.0
        assert m.recall == 1.0
        assert m.f1 == 1.0
        assert m.accuracy == 1.0
        assert m.fpr == 0.0
        assert m.confusion.tp == 2
        assert m.confusion.tn == 2
        assert m.confusion.fp == 0
        assert m.confusion.fn == 0

    def test_all_wrong(self) -> None:
        scores = [0.1, 0.2, 0.9, 0.8]
        labels = [True, True, False, False]
        m = compute_metrics(scores, labels, 0.5)
        assert m.precision == 0.0
        assert m.recall == 0.0
        assert m.f1 == 0.0
        assert m.confusion.fp == 2
        assert m.confusion.fn == 2

    def test_mixed_results(self) -> None:
        scores = [0.9, 0.3, 0.8, 0.1]
        labels = [True, True, False, False]
        m = compute_metrics(scores, labels, 0.5)
        # TP=1, FN=1, FP=1, TN=1
        assert m.confusion.tp == 1
        assert m.confusion.fn == 1
        assert m.confusion.fp == 1
        assert m.confusion.tn == 1
        assert m.precision == 0.5
        assert m.recall == 0.5
        assert m.accuracy == 0.5

    def test_empty_inputs(self) -> None:
        m = compute_metrics([], [], 0.5)
        assert m.f1 == 0.0
        assert m.accuracy == 0.0

    def test_mismatched_lengths(self) -> None:
        with pytest.raises(ValueError, match="same length"):
            compute_metrics([0.5], [True, False])

    def test_threshold_boundary(self) -> None:
        # Score exactly at threshold should be positive
        m = compute_metrics([0.5], [True], 0.5)
        assert m.confusion.tp == 1

        m = compute_metrics([0.49], [True], 0.5)
        assert m.confusion.fn == 1


class TestThresholdSweep:
    def test_default_thresholds(self) -> None:
        results = threshold_sweep([0.5, 0.5], [True, False])
        assert len(results) == 9  # 0.1 to 0.9
        assert results[0].threshold == pytest.approx(0.1)
        assert results[-1].threshold == pytest.approx(0.9)

    def test_custom_thresholds(self) -> None:
        results = threshold_sweep([0.5], [True], thresholds=[0.3, 0.7])
        assert len(results) == 2


class TestPerBranchMetrics:
    def test_basic(self) -> None:
        branch_scores = {
            "branch_a": [0.9, 0.8, 0.1, 0.2],
            "branch_b": [0.6, 0.4, 0.3, 0.7],
        }
        labels = [True, True, False, False]
        results = per_branch_metrics(branch_scores, labels)
        assert "branch_a" in results
        assert "branch_b" in results
        assert results["branch_a"].f1 == 1.0  # perfect
        assert results["branch_b"].f1 < 1.0  # imperfect

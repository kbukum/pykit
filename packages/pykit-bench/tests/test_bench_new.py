"""Comprehensive tests for pykit.bench module."""

from __future__ import annotations

import io
import json
import math
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest

from pykit_bench.bench_cli import BenchCliRunner
from pykit_bench.curves import (
    CalibrationCurve,
    ConfusionMatrixDetail,
    PrecisionRecallCurve,
    RocCurve,
    ScoreDistribution,
    ThresholdPoint,
)
from pykit_bench.evaluator import EvaluatorFunc
from pykit_bench.metric.base import MetricSuite
from pykit_bench.metric.classification import (
    binary_classification,
    confusion_matrix,
    multi_class_classification,
    threshold_sweep,
)
from pykit_bench.metric.composite import weighted
from pykit_bench.metric.matching import exact_match, fuzzy_match
from pykit_bench.metric.probability import auc_roc, brier_score, calibration, log_loss
from pykit_bench.metric.ranking import (
    mean_average_precision,
    ndcg,
    precision_at_k,
    recall_at_k,
)
from pykit_bench.metric.regression import mae, mse, r_squared, rmse
from pykit_bench.middleware import (
    CachingMiddleware,
    TimingMiddleware,
    with_caching,
    with_timing,
)
from pykit_bench.report_gen import (
    CsvReporter,
    JsonReporter,
    JUnitReporter,
    MarkdownReporter,
    TableReporter,
    VegaLiteReporter,
    vegalite_specs,
)
from pykit_bench.result import (
    BenchRunResult,
    BenchRunSummary,
    BenchSampleResult,
    BranchResult,
    DatasetInfo,
    MetricResult,
)
from pykit_bench.run_comparator import BenchRunComparator, MetricChange, RunDiff
from pykit_bench.run_storage import FileRunStorage, ListOptions
from pykit_bench.schema import SCHEMA_URL, SCHEMA_VERSION
from pykit_bench.types import BenchSample, Prediction, ScoredSample, string_label_mapper

if TYPE_CHECKING:
    from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_scored(id: str, true_label: str, pred_label: str, score: float) -> ScoredSample[str]:
    return ScoredSample(
        sample=BenchSample(id=id, label=true_label, input=b"test"),
        prediction=Prediction(label=pred_label, score=score, sample_id=id),
    )


def make_regression_scored(id: str, actual: float, predicted: float) -> ScoredSample[float]:
    return ScoredSample(
        sample=BenchSample(id=id, label=actual, input=b""),
        prediction=Prediction(label=actual, score=predicted, sample_id=id),
    )


def sample_run_result() -> BenchRunResult:
    return BenchRunResult(
        id="test-run-001",
        timestamp=datetime(2025, 1, 1, tzinfo=UTC),
        tag="test",
        duration_ms=1000,
        dataset=DatasetInfo(
            name="test-ds",
            sample_count=4,
            label_distribution={"pos": 2, "neg": 2},
        ),
        metrics=[
            MetricResult(name="accuracy", value=0.75, values={"f1": 0.8}),
        ],
        branches={
            "main": BranchResult(name="main", metrics={"accuracy": 0.75}),
        },
        samples=[
            BenchSampleResult(id="s1", label="pos", predicted="pos", score=0.9, correct=True),
            BenchSampleResult(id="s2", label="neg", predicted="pos", score=0.6, correct=False),
            BenchSampleResult(id="s3", label="pos", predicted="pos", score=0.85, correct=True),
            BenchSampleResult(id="s4", label="neg", predicted="neg", score=0.2, correct=True),
        ],
    )


# ===================================================================
# 1. Core Types
# ===================================================================


class TestCoreTypes:
    def test_bench_sample_defaults(self) -> None:
        s = BenchSample(id="s1", label="pos")
        assert s.id == "s1"
        assert s.label == "pos"
        assert s.input == b""
        assert s.source == ""
        assert s.metadata == {}

    def test_bench_sample_with_input_bytes(self) -> None:
        s = BenchSample(id="s2", label="neg", input=b"\x00\xff")
        assert isinstance(s.input, bytes)
        assert s.input == b"\x00\xff"

    def test_prediction_defaults(self) -> None:
        p = Prediction(label="pos")
        assert p.label == "pos"
        assert p.score == 0.0
        assert p.sample_id == ""
        assert p.scores == {}
        assert p.metadata == {}

    def test_prediction_with_scores(self) -> None:
        p = Prediction(
            label="pos",
            score=0.9,
            sample_id="s1",
            scores={"pos": 0.9, "neg": 0.1},
        )
        assert p.scores["pos"] == 0.9

    def test_scored_sample(self) -> None:
        ss = make_scored("s1", "pos", "pos", 0.9)
        assert ss.sample.id == "s1"
        assert ss.prediction.label == "pos"

    def test_string_label_mapper(self) -> None:
        assert string_label_mapper("hello") == "hello"
        assert string_label_mapper("") == ""

    def test_metadata_isolation(self) -> None:
        """Default factory dicts should not be shared between instances."""
        s1 = BenchSample(id="a", label="x")
        s2 = BenchSample(id="b", label="y")
        s1.metadata["key"] = "val"
        assert "key" not in s2.metadata


# ===================================================================
# 2. Evaluator
# ===================================================================


class TestEvaluator:
    @pytest.mark.asyncio
    async def test_evaluator_func_name(self) -> None:
        async def classify(data: bytes) -> Prediction[str]:
            return Prediction(label="pos", score=0.95)

        ev = EvaluatorFunc("test-model", classify)
        assert ev.name == "test-model"

    @pytest.mark.asyncio
    async def test_evaluator_func_is_available(self) -> None:
        async def classify(data: bytes) -> Prediction[str]:
            return Prediction(label="pos")

        ev = EvaluatorFunc("test-model", classify)
        assert await ev.is_available() is True

    @pytest.mark.asyncio
    async def test_evaluator_func_evaluate(self) -> None:
        async def classify(data: bytes) -> Prediction[str]:
            text = data.decode()
            label = "pos" if "good" in text else "neg"
            return Prediction(label=label, score=0.8, sample_id="s1")

        ev = EvaluatorFunc("classifier", classify)
        result = await ev.evaluate(b"this is good")
        assert result.label == "pos"
        assert result.score == 0.8

        result2 = await ev.evaluate(b"this is bad")
        assert result2.label == "neg"


# ===================================================================
# 3. Metrics — Classification
# ===================================================================


class TestBinaryClassification:
    def test_perfect_classification(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.9),
            make_scored("2", "pos", "pos", 0.8),
            make_scored("3", "neg", "neg", 0.2),
            make_scored("4", "neg", "neg", 0.1),
        ]
        m = binary_classification("pos")
        result = m.compute(scored)
        assert result.name == "binary_classification"
        assert result.values["precision"] == 1.0
        assert result.values["recall"] == 1.0
        assert result.values["f1"] == 1.0
        assert result.values["accuracy"] == 1.0
        assert result.values["tp"] == 2.0
        assert result.values["tn"] == 2.0
        assert result.values["fp"] == 0.0
        assert result.values["fn"] == 0.0

    def test_all_wrong(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.2),  # below threshold → FN
            make_scored("2", "pos", "pos", 0.3),  # below threshold → FN
            make_scored("3", "neg", "neg", 0.8),  # above threshold → FP
            make_scored("4", "neg", "neg", 0.9),  # above threshold → FP
        ]
        m = binary_classification("pos", threshold=0.5)
        result = m.compute(scored)
        assert result.values["precision"] == 0.0
        assert result.values["recall"] == 0.0
        assert result.values["f1"] == 0.0
        assert result.values["tp"] == 0.0
        assert result.values["fn"] == 2.0
        assert result.values["fp"] == 2.0

    def test_mixed_results(self) -> None:
        # 1 TP, 1 FP, 1 TN, 1 FN
        scored = [
            make_scored("1", "pos", "pos", 0.9),  # TP
            make_scored("2", "pos", "pos", 0.3),  # FN (below threshold)
            make_scored("3", "neg", "neg", 0.7),  # FP (above threshold)
            make_scored("4", "neg", "neg", 0.1),  # TN
        ]
        m = binary_classification("pos", threshold=0.5)
        result = m.compute(scored)
        assert result.values["tp"] == 1.0
        assert result.values["fn"] == 1.0
        assert result.values["fp"] == 1.0
        assert result.values["tn"] == 1.0
        assert result.values["precision"] == pytest.approx(0.5)
        assert result.values["recall"] == pytest.approx(0.5)
        assert result.values["f1"] == pytest.approx(0.5)
        assert result.values["accuracy"] == pytest.approx(0.5)

    def test_empty_input(self) -> None:
        m = binary_classification("pos")
        result = m.compute([])
        assert result.value == 0.0

    def test_confusion_matrix_detail(self) -> None:
        scored = [make_scored("1", "pos", "pos", 0.9)]
        m = binary_classification("pos")
        result = m.compute(scored)
        assert result.detail is not None
        assert isinstance(result.detail, ConfusionMatrixDetail)
        assert result.detail.labels == ["pos", "not_pos"]


class TestMultiClassClassification:
    def test_perfect(self) -> None:
        scored = [
            make_scored("1", "cat", "cat", 0.9),
            make_scored("2", "dog", "dog", 0.8),
            make_scored("3", "bird", "bird", 0.7),
        ]
        m = multi_class_classification(["cat", "dog", "bird"])
        result = m.compute(scored)
        assert result.name == "multi_class_classification"
        assert result.values["accuracy"] == pytest.approx(1.0)
        assert result.values["macro_f1"] == pytest.approx(1.0)

    def test_all_wrong(self) -> None:
        scored = [
            make_scored("1", "cat", "dog", 0.9),
            make_scored("2", "dog", "cat", 0.8),
        ]
        m = multi_class_classification(["cat", "dog"])
        result = m.compute(scored)
        assert result.values["accuracy"] == pytest.approx(0.0)

    def test_empty(self) -> None:
        m = multi_class_classification(["a", "b"])
        result = m.compute([])
        assert result.value == 0.0


class TestConfusionMatrix:
    def test_basic(self) -> None:
        scored = [
            make_scored("1", "cat", "cat", 0.9),
            make_scored("2", "dog", "cat", 0.8),
            make_scored("3", "dog", "dog", 0.7),
        ]
        m = confusion_matrix(["cat", "dog"])
        result = m.compute(scored)
        assert result.detail is not None
        assert isinstance(result.detail, ConfusionMatrixDetail)
        # row=actual, col=predicted
        assert result.detail.matrix[0][0] == 1  # cat→cat
        assert result.detail.matrix[1][0] == 1  # dog→cat
        assert result.detail.matrix[1][1] == 1  # dog→dog


class TestThresholdSweep:
    def test_basic(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.9),
            make_scored("2", "pos", "pos", 0.6),
            make_scored("3", "neg", "neg", 0.3),
            make_scored("4", "neg", "neg", 0.1),
        ]
        m = threshold_sweep("pos")
        result = m.compute(scored)
        assert result.name == "threshold_sweep"
        assert result.detail is not None
        assert isinstance(result.detail, list)
        assert len(result.detail) == 9  # 0.1 to 0.9

    def test_custom_thresholds(self) -> None:
        scored = [make_scored("1", "pos", "pos", 0.5)]
        m = threshold_sweep("pos", thresholds=[0.3, 0.7])
        result = m.compute(scored)
        assert len(result.detail) == 2

    def test_empty(self) -> None:
        m = threshold_sweep("pos")
        result = m.compute([])
        assert result.value == 0.0


# ===================================================================
# 3b. Metrics — Matching
# ===================================================================


class TestExactMatch:
    def test_all_match(self) -> None:
        scored = [
            make_scored("1", "hello", "hello", 1.0),
            make_scored("2", "world", "world", 1.0),
        ]
        m = exact_match()
        result = m.compute(scored)
        assert result.value == pytest.approx(1.0)

    def test_none_match(self) -> None:
        scored = [
            make_scored("1", "hello", "bye", 0.5),
            make_scored("2", "world", "moon", 0.5),
        ]
        m = exact_match()
        result = m.compute(scored)
        assert result.value == pytest.approx(0.0)

    def test_half_match(self) -> None:
        scored = [
            make_scored("1", "yes", "yes", 1.0),
            make_scored("2", "no", "maybe", 0.5),
        ]
        m = exact_match()
        result = m.compute(scored)
        assert result.value == pytest.approx(0.5)

    def test_empty(self) -> None:
        m = exact_match()
        assert m.compute([]).value == 0.0


class TestFuzzyMatch:
    def test_identical_strings(self) -> None:
        scored = [make_scored("1", "hello", "hello", 1.0)]
        m = fuzzy_match(threshold=0.8)
        result = m.compute(scored)
        assert result.value == pytest.approx(1.0)
        assert result.values["mean_similarity"] == pytest.approx(1.0)

    def test_similar_above_threshold(self) -> None:
        # "hello" vs "hallo" → distance=1, len=5, similarity=0.8
        scored = [make_scored("1", "hello", "hallo", 1.0)]
        m = fuzzy_match(threshold=0.8)
        result = m.compute(scored)
        assert result.value == pytest.approx(1.0)

    def test_dissimilar_below_threshold(self) -> None:
        scored = [make_scored("1", "hello", "xyz", 0.5)]
        m = fuzzy_match(threshold=0.8)
        result = m.compute(scored)
        assert result.value == pytest.approx(0.0)

    def test_empty(self) -> None:
        m = fuzzy_match()
        assert m.compute([]).value == 0.0


# ===================================================================
# 3c. Metrics — Regression
# ===================================================================


class TestRegression:
    @pytest.fixture
    def scored(self) -> list[ScoredSample[float]]:
        return [
            make_regression_scored("1", 1.0, 1.1),
            make_regression_scored("2", 2.0, 2.1),
            make_regression_scored("3", 3.0, 2.9),
            make_regression_scored("4", 4.0, 4.2),
        ]

    def test_mae(self, scored: list[ScoredSample[float]]) -> None:
        m = mae()
        result = m.compute(scored)
        assert result.name == "mae"
        # (0.1 + 0.1 + 0.1 + 0.2) / 4 = 0.125
        assert result.value == pytest.approx(0.125)

    def test_mse(self, scored: list[ScoredSample[float]]) -> None:
        m = mse()
        result = m.compute(scored)
        assert result.name == "mse"
        # (0.01 + 0.01 + 0.01 + 0.04) / 4 = 0.0175
        assert result.value == pytest.approx(0.0175)

    def test_rmse(self, scored: list[ScoredSample[float]]) -> None:
        m = rmse()
        result = m.compute(scored)
        assert result.name == "rmse"
        assert result.value == pytest.approx(math.sqrt(0.0175), rel=1e-4)

    def test_r_squared(self, scored: list[ScoredSample[float]]) -> None:
        m = r_squared()
        result = m.compute(scored)
        assert result.name == "r_squared"
        # mean_actual = 2.5
        # ss_res = (1-1.1)^2 + (2-2.1)^2 + (3-2.9)^2 + (4-4.2)^2
        #        = 0.01 + 0.01 + 0.01 + 0.04 = 0.07
        # ss_tot = (1-2.5)^2 + (2-2.5)^2 + (3-2.5)^2 + (4-2.5)^2
        #        = 2.25 + 0.25 + 0.25 + 2.25 = 5.0
        # r2 = 1 - 0.07/5.0 = 1 - 0.014 = 0.986
        assert result.value == pytest.approx(0.986, rel=1e-3)
        assert result.values["ss_res"] == pytest.approx(0.07)
        assert result.values["ss_tot"] == pytest.approx(5.0)

    def test_empty(self) -> None:
        assert mae().compute([]).value == 0.0
        assert mse().compute([]).value == 0.0
        assert rmse().compute([]).value == 0.0
        assert r_squared().compute([]).value == 0.0


# ===================================================================
# 3d. Metrics — Probability
# ===================================================================


class TestAucRoc:
    def test_perfect_separation(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.9),
            make_scored("2", "pos", "pos", 0.8),
            make_scored("3", "neg", "neg", 0.2),
            make_scored("4", "neg", "neg", 0.1),
        ]
        m = auc_roc("pos")
        result = m.compute(scored)
        assert result.name == "auc_roc"
        assert result.value == pytest.approx(1.0)
        assert isinstance(result.detail, RocCurve)
        assert result.detail.auc == pytest.approx(1.0)

    def test_random(self) -> None:
        """Alternating labels → AUC near 0.5."""
        scored = [
            make_scored("1", "pos", "pos", 0.9),
            make_scored("2", "neg", "neg", 0.8),
            make_scored("3", "pos", "pos", 0.7),
            make_scored("4", "neg", "neg", 0.6),
        ]
        m = auc_roc("pos")
        result = m.compute(scored)
        assert 0.0 < result.value <= 1.0

    def test_empty(self) -> None:
        m = auc_roc("pos")
        assert m.compute([]).value == 0.0

    def test_all_same_label(self) -> None:
        scored = [make_scored("1", "pos", "pos", 0.9)]
        m = auc_roc("pos")
        result = m.compute(scored)
        assert result.value == 0.0  # no negatives


class TestBrierScore:
    def test_perfect(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 1.0),
            make_scored("2", "neg", "neg", 0.0),
        ]
        m = brier_score("pos")
        result = m.compute(scored)
        assert result.value == pytest.approx(0.0)

    def test_worst(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.0),
            make_scored("2", "neg", "neg", 1.0),
        ]
        m = brier_score("pos")
        result = m.compute(scored)
        assert result.value == pytest.approx(1.0)

    def test_empty(self) -> None:
        assert brier_score("pos").compute([]).value == 0.0


class TestLogLoss:
    def test_near_perfect(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.99),
            make_scored("2", "neg", "neg", 0.01),
        ]
        m = log_loss("pos")
        result = m.compute(scored)
        assert result.value > 0.0
        assert result.value < 0.1  # near-perfect should be low

    def test_empty(self) -> None:
        assert log_loss("pos").compute([]).value == 0.0


class TestCalibration:
    def test_basic(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.9),
            make_scored("2", "neg", "neg", 0.1),
        ]
        m = calibration("pos", bins=10)
        result = m.compute(scored)
        assert result.name == "calibration"
        assert isinstance(result.detail, CalibrationCurve)
        assert len(result.detail.bin_count) == 10

    def test_empty(self) -> None:
        assert calibration("pos").compute([]).value == 0.0


# ===================================================================
# 3e. Metrics — Ranking
# ===================================================================


class TestRanking:
    def test_ndcg_perfect(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.9),
            make_scored("2", "pos", "pos", 0.8),
            make_scored("3", "neg", "neg", 0.1),
        ]
        m = ndcg()
        result = m.compute(scored)
        assert result.name == "ndcg"
        assert result.value == pytest.approx(1.0)

    def test_ndcg_with_k(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.9),
            make_scored("2", "neg", "neg", 0.8),
            make_scored("3", "pos", "pos", 0.1),
        ]
        m = ndcg(k=2)
        result = m.compute(scored)
        assert result.name == "ndcg@2"
        assert 0.0 <= result.value <= 1.0

    def test_mean_average_precision(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.9),
            make_scored("2", "neg", "neg", 0.8),
            make_scored("3", "pos", "pos", 0.7),
        ]
        m = mean_average_precision("pos")
        result = m.compute(scored)
        assert result.name == "mean_average_precision"
        # Sorted by score desc: pos@1, neg@2, pos@3
        # precision at pos1: 1/1=1.0, precision at pos3: 2/3=0.667
        # MAP = (1.0 + 2/3) / 2 = 0.8333
        assert result.value == pytest.approx(5.0 / 6.0, rel=1e-3)

    def test_precision_at_k(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.9),
            make_scored("2", "neg", "neg", 0.8),
            make_scored("3", "pos", "pos", 0.7),
        ]
        m = precision_at_k("pos", k=2)
        result = m.compute(scored)
        assert result.name == "precision@2"
        # top 2 by score: pos(0.9), neg(0.8) → 1 relevant out of 2
        assert result.value == pytest.approx(0.5)

    def test_recall_at_k(self) -> None:
        scored = [
            make_scored("1", "pos", "pos", 0.9),
            make_scored("2", "neg", "neg", 0.8),
            make_scored("3", "pos", "pos", 0.7),
        ]
        m = recall_at_k("pos", k=2)
        result = m.compute(scored)
        assert result.name == "recall@2"
        # top 2: pos, neg → 1 relevant out of 2 total relevant
        assert result.value == pytest.approx(0.5)

    def test_empty_ranking(self) -> None:
        assert ndcg().compute([]).value == 0.0
        assert mean_average_precision("pos").compute([]).value == 0.0
        assert precision_at_k("pos", k=5).compute([]).value == 0.0
        assert recall_at_k("pos", k=5).compute([]).value == 0.0


# ===================================================================
# 3f. Metrics — Composite
# ===================================================================


class TestComposite:
    def test_weighted(self) -> None:
        scored = [
            make_scored("1", "hello", "hello", 1.0),
            make_scored("2", "world", "world", 1.0),
        ]
        em = exact_match()
        fm = fuzzy_match(threshold=0.8)
        m = weighted({em: 0.6, fm: 0.4})
        result = m.compute(scored)
        assert "weighted(" in result.name
        # exact_match=1.0, fuzzy_match=1.0 → 0.6*1.0 + 0.4*1.0 = 1.0
        assert result.value == pytest.approx(1.0)
        assert "exact_match" in result.values
        assert "fuzzy_match" in result.values


# ===================================================================
# 3g. MetricSuite
# ===================================================================


class TestMetricSuite:
    def test_compute_all(self) -> None:
        scored = [
            make_scored("1", "hello", "hello", 1.0),
            make_scored("2", "world", "moon", 0.5),
        ]
        suite = MetricSuite([exact_match(), fuzzy_match()])
        results = suite.compute(scored)
        assert len(results) == 2
        names = {r.name for r in results}
        assert "exact_match" in names
        assert "fuzzy_match" in names

    def test_add_metric(self) -> None:
        suite: MetricSuite[str] = MetricSuite()
        suite.add(exact_match())
        scored = [make_scored("1", "a", "a", 1.0)]
        results = suite.compute(scored)
        assert len(results) == 1
        assert results[0].name == "exact_match"

    def test_empty_suite(self) -> None:
        suite: MetricSuite[str] = MetricSuite()
        results = suite.compute([make_scored("1", "a", "a", 1.0)])
        assert results == []


# ===================================================================
# 4. Run Comparator
# ===================================================================


class TestCompare:
    def test_metric_change_detected(self) -> None:
        base = sample_run_result()
        target = BenchRunResult(
            id="test-run-002",
            timestamp=datetime(2025, 1, 2, tzinfo=UTC),
            tag="test",
            duration_ms=900,
            dataset=DatasetInfo(name="test-ds", sample_count=4),
            metrics=[
                MetricResult(name="accuracy", value=0.85, values={"f1": 0.9}),
            ],
            samples=[
                BenchSampleResult(id="s1", label="pos", predicted="pos", score=0.9, correct=True),
                BenchSampleResult(id="s2", label="neg", predicted="neg", score=0.3, correct=True),
            ],
        )
        comparator = BenchRunComparator(change_threshold=0.01)
        diff = comparator.compare(base, target)
        assert diff.base_id == "test-run-001"
        assert diff.target_id == "test-run-002"
        assert len(diff.changes) > 0

        acc_change = next(c for c in diff.changes if c.name == "accuracy")
        assert acc_change.old_value == pytest.approx(0.75)
        assert acc_change.new_value == pytest.approx(0.85)
        assert acc_change.delta == pytest.approx(0.10)
        assert acc_change.improved is True
        assert acc_change.significant is True

    def test_has_regression(self) -> None:
        diff = RunDiff(
            base_id="a",
            target_id="b",
            changes=[
                MetricChange(
                    name="f1",
                    old_value=0.9,
                    new_value=0.7,
                    delta=-0.2,
                    improved=False,
                    significant=True,
                )
            ],
        )
        assert diff.has_regression() is True

    def test_no_regression(self) -> None:
        diff = RunDiff(
            base_id="a",
            target_id="b",
            changes=[
                MetricChange(
                    name="f1",
                    old_value=0.7,
                    new_value=0.9,
                    delta=0.2,
                    improved=True,
                    significant=True,
                )
            ],
        )
        assert diff.has_regression() is False

    def test_summary_non_empty(self) -> None:
        diff = RunDiff(
            base_id="run-1",
            target_id="run-2",
            changes=[
                MetricChange("acc", 0.7, 0.8, 0.1, True, True),
            ],
            fixed=["s1"],
            regressed=["s2"],
        )
        summary = diff.summary()
        assert "run-1" in summary
        assert "run-2" in summary
        assert "Fixed" in summary
        assert "Regressed" in summary

    def test_fixed_and_regressed_samples(self) -> None:
        base = BenchRunResult(
            id="base",
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            dataset=DatasetInfo(name="ds"),
            metrics=[MetricResult(name="m", value=0.5)],
            samples=[
                BenchSampleResult(id="s1", label="a", correct=False),
                BenchSampleResult(id="s2", label="b", correct=True),
            ],
        )
        target = BenchRunResult(
            id="target",
            timestamp=datetime(2025, 1, 2, tzinfo=UTC),
            dataset=DatasetInfo(name="ds"),
            metrics=[MetricResult(name="m", value=0.5)],
            samples=[
                BenchSampleResult(id="s1", label="a", correct=True),  # fixed
                BenchSampleResult(id="s2", label="b", correct=False),  # regressed
            ],
        )
        diff = BenchRunComparator().compare(base, target)
        assert "s1" in diff.fixed
        assert "s2" in diff.regressed


# ===================================================================
# 5. Reporters
# ===================================================================


class TestReporters:
    @pytest.fixture
    def run_result(self) -> BenchRunResult:
        return sample_run_result()

    def test_markdown(self, run_result: BenchRunResult) -> None:
        w = io.StringIO()
        MarkdownReporter().generate(w, run_result)
        output = w.getvalue()
        assert len(output) > 0
        assert "# Benchmark Report" in output
        assert run_result.id in output

    def test_json_valid(self, run_result: BenchRunResult) -> None:
        w = io.StringIO()
        JsonReporter().generate(w, run_result)
        output = w.getvalue()
        data = json.loads(output)
        assert "$schema" in data
        assert data["$schema"] == SCHEMA_URL
        assert data["id"] == "test-run-001"

    def test_csv(self, run_result: BenchRunResult) -> None:
        w = io.StringIO()
        CsvReporter().generate(w, run_result)
        output = w.getvalue()
        lines = output.strip().split("\n")
        assert len(lines) >= 1
        assert "metric_name" in lines[0]

    def test_junit(self, run_result: BenchRunResult) -> None:
        w = io.StringIO()
        JUnitReporter().generate(w, run_result)
        output = w.getvalue()
        assert "<?xml" in output
        assert "<testsuites>" in output or "<testsuites" in output

    def test_table(self, run_result: BenchRunResult) -> None:
        w = io.StringIO()
        TableReporter().generate(w, run_result)
        output = w.getvalue()
        assert len(output) > 0
        assert "Benchmark Report" in output

    def test_vegalite_reporter(self, run_result: BenchRunResult) -> None:
        w = io.StringIO()
        VegaLiteReporter().generate(w, run_result)
        output = w.getvalue()
        data = json.loads(output)
        assert isinstance(data, dict)

    def test_vegalite_specs_with_samples(self, run_result: BenchRunResult) -> None:
        specs = vegalite_specs(run_result)
        assert isinstance(specs, dict)
        # Should have score_distribution since we have samples
        if "score_distribution" in specs:
            assert "$schema" in specs["score_distribution"]

    def test_vegalite_specs_with_branches(self, run_result: BenchRunResult) -> None:
        specs = vegalite_specs(run_result)
        if "branch_comparison" in specs:
            assert "$schema" in specs["branch_comparison"]

    def test_reporter_names(self) -> None:
        assert MarkdownReporter().name == "markdown"
        assert JsonReporter().name == "json"
        assert CsvReporter().name == "csv"
        assert JUnitReporter().name == "junit"
        assert TableReporter().name == "table"
        assert VegaLiteReporter().name == "vegalite"


# ===================================================================
# 6. Storage
# ===================================================================


class TestStorage:
    def test_save_and_load(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        run = sample_run_result()
        run_id = storage.save(run)
        assert run_id == "test-run-001"

        loaded = storage.load(run_id)
        assert loaded.id == run.id
        assert loaded.tag == run.tag
        assert loaded.dataset.name == run.dataset.name
        assert len(loaded.metrics) == len(run.metrics)
        assert len(loaded.samples) == len(run.samples)

    def test_load_missing(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        with pytest.raises(FileNotFoundError):
            storage.load("nonexistent")

    def test_latest(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        run = sample_run_result()
        storage.save(run)

        latest = storage.latest()
        assert latest.id == run.id

    def test_latest_empty(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        with pytest.raises(FileNotFoundError):
            storage.latest()

    def test_list_runs(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        run = sample_run_result()
        storage.save(run)

        summaries = storage.list_runs()
        assert len(summaries) == 1
        assert summaries[0].id == "test-run-001"
        assert summaries[0].dataset == "test-ds"
        assert summaries[0].tag == "test"

    def test_list_runs_with_options(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        run1 = sample_run_result()
        run2 = BenchRunResult(
            id="test-run-002",
            timestamp=datetime(2025, 1, 2, tzinfo=UTC),
            tag="nightly",
            dataset=DatasetInfo(name="other-ds"),
            metrics=[MetricResult(name="f1", value=0.9, values={"f1": 0.9})],
        )
        storage.save(run1)
        storage.save(run2)

        # Filter by tag
        opts = ListOptions(tag="test")
        filtered = storage.list_runs(opts)
        assert len(filtered) == 1
        assert filtered[0].tag == "test"

        # Filter by dataset
        opts = ListOptions(dataset="other-ds")
        filtered = storage.list_runs(opts)
        assert len(filtered) == 1
        assert filtered[0].dataset == "other-ds"

        # Limit
        opts = ListOptions(limit=1)
        limited = storage.list_runs(opts)
        assert len(limited) == 1

    def test_generate_run_id(self) -> None:
        run_id = FileRunStorage.generate_run_id("mytest")
        assert run_id.startswith("mytest-")
        # Format: mytest-YYYYMMDD-HHMMSS
        assert len(run_id) > len("mytest-")


# ===================================================================
# 7. Schema
# ===================================================================


class TestSchema:
    def test_version(self) -> None:
        assert SCHEMA_VERSION == "1.0"

    def test_url(self) -> None:
        assert "schema.json" in SCHEMA_URL
        assert SCHEMA_URL.startswith("https://")


# ===================================================================
# 8. Curves
# ===================================================================


class TestCurves:
    def test_roc_curve(self) -> None:
        c = RocCurve(fpr=[0.0, 0.5, 1.0], tpr=[0.0, 0.8, 1.0], thresholds=[0.9, 0.5], auc=0.9)
        assert c.auc == 0.9
        assert len(c.fpr) == 3

    def test_precision_recall_curve(self) -> None:
        c = PrecisionRecallCurve(precision=[1.0, 0.8], recall=[0.5, 1.0], thresholds=[0.9])
        assert len(c.precision) == 2

    def test_calibration_curve(self) -> None:
        c = CalibrationCurve(
            predicted_probability=[0.1, 0.9],
            actual_frequency=[0.0, 1.0],
            bin_count=[5, 5],
        )
        assert len(c.bin_count) == 2

    def test_confusion_matrix_detail(self) -> None:
        c = ConfusionMatrixDetail(
            labels=["pos", "neg"],
            matrix=[[10, 2], [3, 15]],
        )
        assert c.orientation == "row=actual, col=predicted"
        assert c.matrix[0][0] == 10

    def test_score_distribution(self) -> None:
        c = ScoreDistribution(label="pos", bins=[0.0, 0.5, 1.0], counts=[3, 7, 2])
        assert c.label == "pos"

    def test_threshold_point(self) -> None:
        p = ThresholdPoint(threshold=0.5, precision=0.8, recall=0.7, f1=0.75, accuracy=0.9)
        assert p.f1 == 0.75


# ===================================================================
# 9. Result Serialization
# ===================================================================


class TestResultSerde:
    def test_model_dump_json_roundtrip(self) -> None:
        run = sample_run_result()
        json_str = run.model_dump_json(by_alias=True)
        data = json.loads(json_str)
        loaded = BenchRunResult.model_validate(data)
        assert loaded.id == run.id
        assert loaded.schema_url == run.schema_url
        assert loaded.version == run.version

    def test_schema_alias(self) -> None:
        run = sample_run_result()
        data = run.model_dump(by_alias=True)
        assert "$schema" in data
        assert data["$schema"] == SCHEMA_URL

    def test_populate_by_name(self) -> None:
        """Can construct BenchRunResult using field name schema_url."""
        run = BenchRunResult(
            id="r1",
            schema_url="https://example.com/schema.json",
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            dataset=DatasetInfo(name="ds"),
        )
        assert run.schema_url == "https://example.com/schema.json"

    def test_populate_by_alias(self) -> None:
        """Can construct BenchRunResult from dict with $schema alias."""
        data = {
            "$schema": "https://example.com/s.json",
            "id": "r1",
            "version": "1.0",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "dataset": {"name": "ds"},
        }
        run = BenchRunResult.model_validate(data)
        assert run.schema_url == "https://example.com/s.json"

    def test_default_schema_values(self) -> None:
        run = BenchRunResult(
            id="r1",
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            dataset=DatasetInfo(name="ds"),
        )
        assert run.schema_url == SCHEMA_URL
        assert run.version == SCHEMA_VERSION

    def test_metric_result_serde(self) -> None:
        m = MetricResult(name="acc", value=0.95, values={"p": 0.9}, detail={"extra": 1})
        data = m.model_dump()
        loaded = MetricResult.model_validate(data)
        assert loaded.name == "acc"
        assert loaded.value == 0.95
        assert loaded.detail == {"extra": 1}

    def test_bench_run_summary(self) -> None:
        s = BenchRunSummary(
            id="r1",
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            tag="v1",
            dataset="ds",
            f1=0.85,
        )
        assert s.f1 == 0.85
        assert s.dataset == "ds"


# ===================================================================
# 10. Middleware
# ===================================================================


class TestMiddleware:
    @pytest.mark.asyncio
    async def test_timing_middleware(self) -> None:
        async def classify(data: bytes) -> Prediction[str]:
            return Prediction(label="pos", score=0.9, sample_id="s1")

        inner = EvaluatorFunc("test", classify)
        timed = TimingMiddleware(inner)

        assert timed.name == "test"
        assert await timed.is_available() is True

        await timed.evaluate(b"hello")
        await timed.evaluate(b"world")

        assert len(timed.timings) == 2
        assert timed.average > 0.0
        for sample_id, elapsed in timed.timings:
            assert sample_id == "s1"
            assert elapsed >= 0.0

    @pytest.mark.asyncio
    async def test_caching_middleware(self) -> None:
        call_count = 0

        async def classify(data: bytes) -> Prediction[str]:
            nonlocal call_count
            call_count += 1
            return Prediction(label="pos", score=0.9, sample_id="s1")

        inner = EvaluatorFunc("test", classify)
        cached = CachingMiddleware(inner)

        assert cached.name == "test"
        assert await cached.is_available() is True

        # First call: miss
        await cached.evaluate(b"hello")
        assert cached.miss_count == 1
        assert cached.hit_count == 0

        # Same input: hit
        await cached.evaluate(b"hello")
        assert cached.hit_count == 1
        assert cached.miss_count == 1
        assert call_count == 1  # underlying only called once

        # Different input: another miss
        await cached.evaluate(b"world")
        assert cached.miss_count == 2

    @pytest.mark.asyncio
    async def test_with_timing_convenience(self) -> None:
        async def classify(data: bytes) -> Prediction[str]:
            return Prediction(label="pos")

        inner = EvaluatorFunc("test", classify)
        timed = with_timing(inner)
        assert isinstance(timed, TimingMiddleware)
        await timed.evaluate(b"data")
        assert len(timed.timings) == 1

    @pytest.mark.asyncio
    async def test_with_caching_convenience(self) -> None:
        async def classify(data: bytes) -> Prediction[str]:
            return Prediction(label="pos")

        inner = EvaluatorFunc("test", classify)
        cached = with_caching(inner)
        assert isinstance(cached, CachingMiddleware)
        await cached.evaluate(b"data")
        assert cached.miss_count == 1


# ===================================================================
# 11. CLI Runner
# ===================================================================


class TestCli:
    def test_list_runs(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        storage.save(sample_run_result())

        cli = BenchCliRunner(tmp_path / "results")
        w = io.StringIO()
        cli.list_runs(w)
        output = w.getvalue()
        assert "test-run-001" in output
        assert "Total:" in output

    def test_list_runs_empty(self, tmp_path: Path) -> None:
        cli = BenchCliRunner(tmp_path / "results")
        w = io.StringIO()
        cli.list_runs(w)
        assert "No runs found" in w.getvalue()

    def test_show_latest(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        storage.save(sample_run_result())

        cli = BenchCliRunner(tmp_path / "results")
        w = io.StringIO()
        cli.show_latest(w)
        output = w.getvalue()
        assert "test-run-001" in output

    def test_show_run(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        storage.save(sample_run_result())

        cli = BenchCliRunner(tmp_path / "results")
        w = io.StringIO()
        cli.show_run(w, "test-run-001")
        assert "test-run-001" in w.getvalue()

    def test_compare_runs(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        run1 = sample_run_result()
        run2 = BenchRunResult(
            id="test-run-002",
            timestamp=datetime(2025, 1, 2, tzinfo=UTC),
            tag="test",
            dataset=DatasetInfo(name="test-ds"),
            metrics=[
                MetricResult(name="accuracy", value=0.85, values={"f1": 0.9}),
            ],
            samples=[
                BenchSampleResult(id="s1", label="pos", predicted="pos", score=0.95, correct=True),
                BenchSampleResult(id="s2", label="neg", predicted="neg", score=0.3, correct=True),
            ],
        )
        storage.save(run1)
        storage.save(run2)

        cli = BenchCliRunner(tmp_path / "results")
        w = io.StringIO()
        cli.compare_runs(w, "test-run-001", "test-run-002")
        output = w.getvalue()
        assert "test-run-001" in output
        assert "test-run-002" in output

    def test_compare_latest(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        run1 = sample_run_result()
        run2 = BenchRunResult(
            id="test-run-002",
            timestamp=datetime(2025, 1, 2, tzinfo=UTC),
            tag="test",
            dataset=DatasetInfo(name="test-ds"),
            metrics=[MetricResult(name="accuracy", value=0.9, values={"f1": 0.9})],
        )
        storage.save(run1)
        storage.save(run2)

        cli = BenchCliRunner(tmp_path / "results")
        w = io.StringIO()
        cli.compare_latest(w)
        output = w.getvalue()
        assert len(output) > 0

    def test_compare_latest_needs_two_runs(self, tmp_path: Path) -> None:
        storage = FileRunStorage(tmp_path / "results")
        storage.save(sample_run_result())
        cli = BenchCliRunner(tmp_path / "results")
        with pytest.raises(ValueError, match="at least 2 runs"):
            cli.compare_latest(io.StringIO())

"""Tests for evaluator.py — EvaluatorFunc, FromProvider, and protocol."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

from pykit_bench.evaluator import Evaluator, EvaluatorFunc, FromProvider
from pykit_bench.types import Prediction

# ---------------------------------------------------------------------------
# EvaluatorFunc
# ---------------------------------------------------------------------------


class TestEvaluatorFunc:
    def test_name(self):
        async def dummy(data: bytes) -> Prediction[str]:
            return Prediction(label="a", score=0.5)

        ev = EvaluatorFunc("my-eval", dummy)
        assert ev.name == "my-eval"

    def test_is_available(self):
        async def dummy(data: bytes) -> Prediction[str]:
            return Prediction(label="a", score=0.5)

        ev = EvaluatorFunc("test", dummy)
        result = asyncio.get_event_loop().run_until_complete(ev.is_available())
        assert result is True

    def test_evaluate(self):
        async def classify(data: bytes) -> Prediction[str]:
            return Prediction(label="positive", score=0.95)

        ev = EvaluatorFunc("classifier", classify)
        pred = asyncio.get_event_loop().run_until_complete(ev.evaluate(b"test data"))
        assert pred.label == "positive"
        assert pred.score == 0.95

    def test_satisfies_protocol(self):
        async def dummy(data: bytes) -> Prediction[str]:
            return Prediction(label="a", score=0.5)

        ev = EvaluatorFunc("test", dummy)
        assert isinstance(ev, Evaluator)


# ---------------------------------------------------------------------------
# FromProvider
# ---------------------------------------------------------------------------


class TestFromProvider:
    def _make_provider(self):
        provider = MagicMock()
        provider.name = "grpc-provider"
        provider.is_available = AsyncMock(return_value=True)
        provider.execute = AsyncMock(return_value={"label": "pos", "score": 0.88})
        return provider

    def test_name(self):
        provider = self._make_provider()
        ev = FromProvider(
            provider=provider,
            to_input=lambda raw: raw,
            to_prediction=lambda resp: Prediction(label=resp["label"], score=resp["score"]),
        )
        assert ev.name == "grpc-provider"

    def test_is_available(self):
        provider = self._make_provider()
        ev = FromProvider(
            provider=provider,
            to_input=lambda raw: raw,
            to_prediction=lambda resp: Prediction(label=resp["label"], score=resp["score"]),
        )
        result = asyncio.get_event_loop().run_until_complete(ev.is_available())
        assert result is True

    def test_evaluate(self):
        provider = self._make_provider()
        ev = FromProvider(
            provider=provider,
            to_input=lambda raw: {"data": raw},
            to_prediction=lambda resp: Prediction(label=resp["label"], score=resp["score"]),
        )
        pred = asyncio.get_event_loop().run_until_complete(ev.evaluate(b"input"))
        assert pred.label == "pos"
        assert pred.score == 0.88
        provider.execute.assert_awaited_once_with({"data": b"input"})

    def test_satisfies_protocol(self):
        provider = self._make_provider()
        ev = FromProvider(
            provider=provider,
            to_input=lambda raw: raw,
            to_prediction=lambda resp: Prediction(label="x", score=0.0),
        )
        assert isinstance(ev, Evaluator)

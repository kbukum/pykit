"""Tests for pykit_logging.sampling."""

from __future__ import annotations

import threading
import time
from typing import Any
from unittest.mock import patch

import structlog

from pykit_logging.sampling import LogSampler, SamplingConfig, sampling_processor

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event_dict(**kwargs: Any) -> dict[str, Any]:
    """Build a minimal structlog event_dict for processor tests."""
    return kwargs


# ---------------------------------------------------------------------------
# SamplingConfig defaults
# ---------------------------------------------------------------------------


class TestSamplingConfig:
    def test_defaults(self) -> None:
        cfg = SamplingConfig()
        assert cfg.enabled is False
        assert cfg.initial_rate == 100
        assert cfg.thereafter_rate == 100

    def test_custom_values(self) -> None:
        cfg = SamplingConfig(enabled=True, initial_rate=5, thereafter_rate=10)
        assert cfg.enabled is True
        assert cfg.initial_rate == 5
        assert cfg.thereafter_rate == 10


# ---------------------------------------------------------------------------
# LogSampler core behaviour
# ---------------------------------------------------------------------------


class TestLogSampler:
    def test_disabled_allows_everything(self) -> None:
        sampler = LogSampler(SamplingConfig(enabled=False))
        for _ in range(500):
            assert sampler.should_log("info") is True

    def test_allows_initial_burst(self) -> None:
        sampler = LogSampler(SamplingConfig(enabled=True, initial_rate=5, thereafter_rate=10))
        for _ in range(5):
            assert sampler.should_log("info") is True

    def test_drops_after_burst(self) -> None:
        sampler = LogSampler(SamplingConfig(enabled=True, initial_rate=3, thereafter_rate=5))
        # Consume the initial burst
        for _ in range(3):
            sampler.should_log("info")

        # After burst: messages 4, 5, 6, 7 should be dropped; 8 passes (every 5th overflow)
        results = [sampler.should_log("info") for _ in range(5)]
        # overflow counts: 1,2,3,4,5 → only 5 (divisible by 5) passes
        assert results == [False, False, False, False, True]

    def test_thereafter_rate_allows_every_nth(self) -> None:
        sampler = LogSampler(SamplingConfig(enabled=True, initial_rate=0, thereafter_rate=3))
        results = [sampler.should_log("info") for _ in range(9)]
        # All are overflow; overflow 3,6,9 pass
        assert results == [False, False, True, False, False, True, False, False, True]

    def test_per_level_independent(self) -> None:
        sampler = LogSampler(SamplingConfig(enabled=True, initial_rate=2, thereafter_rate=100))
        # "info" burst
        assert sampler.should_log("info") is True
        assert sampler.should_log("info") is True
        assert sampler.should_log("info") is False  # burst exhausted

        # "error" still has its own budget
        assert sampler.should_log("error") is True
        assert sampler.should_log("error") is True
        assert sampler.should_log("error") is False

    def test_counter_resets_after_one_second(self) -> None:
        sampler = LogSampler(SamplingConfig(enabled=True, initial_rate=2, thereafter_rate=100))
        assert sampler.should_log("info") is True
        assert sampler.should_log("info") is True
        assert sampler.should_log("info") is False

        # Simulate clock advancing past the 1-second window
        with patch("pykit_logging.sampling.time") as mock_time:
            mock_time.monotonic.return_value = time.monotonic() + 2.0
            assert sampler.should_log("info") is True

    def test_thread_safety(self) -> None:
        """Multiple threads hammering the sampler should not corrupt state."""
        sampler = LogSampler(SamplingConfig(enabled=True, initial_rate=10, thereafter_rate=5))
        errors: list[Exception] = []

        def _worker() -> None:
            try:
                for _ in range(200):
                    sampler.should_log("info")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=_worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []


# ---------------------------------------------------------------------------
# sampling_processor integration
# ---------------------------------------------------------------------------


class TestSamplingProcessor:
    def test_disabled_passes_through(self) -> None:
        proc = sampling_processor(SamplingConfig(enabled=False))
        ed = _make_event_dict(event="hello", level="info")
        result = proc(None, "info", ed)  # type: ignore[arg-type]
        assert result["event"] == "hello"

    def test_drops_event_when_sampled_out(self) -> None:
        proc = sampling_processor(SamplingConfig(enabled=True, initial_rate=1, thereafter_rate=100))
        ed1 = _make_event_dict(event="first", level="info")
        result = proc(None, "info", ed1)  # type: ignore[arg-type]
        assert result["event"] == "first"

        # Second event in same window should be dropped
        ed2 = _make_event_dict(event="second", level="info")
        try:
            proc(None, "info", ed2)  # type: ignore[arg-type]
            raised = False
        except structlog.DropEvent:
            raised = True
        assert raised, "Expected DropEvent for sampled-out message"

    def test_default_config_disables_sampling(self) -> None:
        proc = sampling_processor()
        for _ in range(500):
            ed = _make_event_dict(event="msg", level="info")
            result = proc(None, "info", ed)  # type: ignore[arg-type]
            assert result["event"] == "msg"

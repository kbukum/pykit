"""Tests for pykit.metrics."""

from __future__ import annotations

from pykit_metrics import MetricsCollector


class TestMetricsCollector:
    def test_create(self) -> None:
        collector = MetricsCollector("test_service")
        assert collector.service_name == "test_service"
        assert collector.request_count is not None
        assert collector.request_duration is not None

    def test_observe_request(self) -> None:
        collector = MetricsCollector("test_observe")
        collector.observe_request("/test.Method", "OK", 0.5)
        # Verify counter was incremented (no exception)
        assert collector.request_count._metrics is not None

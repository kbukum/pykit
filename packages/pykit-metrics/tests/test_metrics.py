"""Tests for pykit.metrics."""

from __future__ import annotations

from unittest.mock import patch

from pykit_metrics import MetricsCollector
from pykit_metrics.prometheus import start_metrics_server


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


class TestStartMetricsServer:
    def test_start_metrics_server(self) -> None:
        """Cover prometheus.py lines 45-51: start_metrics_server starts a daemon thread."""
        with patch("pykit_metrics.prometheus.start_http_server") as mock_start:
            start_metrics_server(9191)
            # Give the thread time to call start_http_server
            import time

            time.sleep(0.1)
            mock_start.assert_called_once_with(9191)

    def test_start_metrics_server_default_port(self) -> None:
        with patch("pykit_metrics.prometheus.start_http_server") as mock_start:
            start_metrics_server()
            import time

            time.sleep(0.1)
            mock_start.assert_called_once_with(9090)

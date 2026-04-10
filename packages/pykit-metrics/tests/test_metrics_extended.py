"""Extended tests for pykit-metrics: metric values, labels, edge cases."""

from __future__ import annotations

from unittest.mock import patch

from prometheus_client import REGISTRY

from pykit_metrics import MetricsCollector
from pykit_metrics.prometheus import start_metrics_server


def _get_sample_value(name: str, labels: dict[str, str]) -> float | None:
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name == name and all(sample.labels.get(k) == v for k, v in labels.items()):
                return sample.value
    return None


# ---------------------------------------------------------------------------
# MetricsCollector construction
# ---------------------------------------------------------------------------


class TestMetricsCollectorConstruction:
    def test_default_service_name(self) -> None:
        mc = MetricsCollector()
        assert mc.service_name == "pykit"

    def test_custom_service_name(self) -> None:
        mc = MetricsCollector("myapp")
        assert mc.service_name == "myapp"

    def test_request_count_is_counter(self) -> None:
        mc = MetricsCollector("ctr_test_svc")
        assert hasattr(mc.request_count, "labels")
        assert hasattr(mc.request_count, "inc")

    def test_request_duration_is_histogram(self) -> None:
        mc = MetricsCollector("hist_test_svc")
        assert hasattr(mc.request_duration, "labels")
        assert hasattr(mc.request_duration, "observe")

    def test_active_requests_is_counter(self) -> None:
        mc = MetricsCollector("active_test_svc")
        assert hasattr(mc.active_requests, "labels")
        assert hasattr(mc.active_requests, "inc")

    def test_metric_names_include_service(self) -> None:
        mc = MetricsCollector("naming_svc")
        # Counter._name stores name without _total suffix (prometheus_client adds it)
        assert "naming_svc_grpc_requests" in mc.request_count._name
        assert "naming_svc_grpc_request_duration_seconds" in mc.request_duration._name
        assert "naming_svc_grpc_active_requests" in mc.active_requests._name


# ---------------------------------------------------------------------------
# observe_request — value verification
# ---------------------------------------------------------------------------


class TestObserveRequest:
    def test_counter_increments(self) -> None:
        mc = MetricsCollector("obs_ctr_svc")
        mc.observe_request("/Method", "OK", 0.1)
        mc.observe_request("/Method", "OK", 0.2)

        val = _get_sample_value(
            "obs_ctr_svc_grpc_requests_total",
            {"method": "/Method", "status": "OK"},
        )
        assert val is not None and val >= 2.0

    def test_counter_different_statuses(self) -> None:
        mc = MetricsCollector("obs_status_svc")
        mc.observe_request("/Foo", "OK", 0.1)
        mc.observe_request("/Foo", "INTERNAL", 0.1)
        mc.observe_request("/Foo", "OK", 0.1)

        ok_val = _get_sample_value(
            "obs_status_svc_grpc_requests_total",
            {"method": "/Foo", "status": "OK"},
        )
        err_val = _get_sample_value(
            "obs_status_svc_grpc_requests_total",
            {"method": "/Foo", "status": "INTERNAL"},
        )
        assert ok_val is not None and ok_val >= 2.0
        assert err_val is not None and err_val >= 1.0

    def test_counter_different_methods(self) -> None:
        mc = MetricsCollector("obs_meth_svc")
        mc.observe_request("/MethodA", "OK", 0.1)
        mc.observe_request("/MethodB", "OK", 0.1)

        val_a = _get_sample_value(
            "obs_meth_svc_grpc_requests_total",
            {"method": "/MethodA", "status": "OK"},
        )
        val_b = _get_sample_value(
            "obs_meth_svc_grpc_requests_total",
            {"method": "/MethodB", "status": "OK"},
        )
        assert val_a is not None and val_a >= 1.0
        assert val_b is not None and val_b >= 1.0

    def test_histogram_duration_recorded(self) -> None:
        mc = MetricsCollector("obs_dur_svc")
        mc.observe_request("/Slow", "OK", 1.5)

        count = _get_sample_value(
            "obs_dur_svc_grpc_request_duration_seconds_count",
            {"method": "/Slow"},
        )
        total = _get_sample_value(
            "obs_dur_svc_grpc_request_duration_seconds_sum",
            {"method": "/Slow"},
        )
        assert count is not None and count >= 1.0
        assert total is not None and total >= 1.5

    def test_histogram_multiple_observations(self) -> None:
        mc = MetricsCollector("obs_multi_svc")
        mc.observe_request("/M", "OK", 0.1)
        mc.observe_request("/M", "OK", 0.2)
        mc.observe_request("/M", "OK", 0.3)

        count = _get_sample_value(
            "obs_multi_svc_grpc_request_duration_seconds_count",
            {"method": "/M"},
        )
        total = _get_sample_value(
            "obs_multi_svc_grpc_request_duration_seconds_sum",
            {"method": "/M"},
        )
        assert count is not None and count >= 3.0
        assert total is not None and total >= 0.6


# ---------------------------------------------------------------------------
# Histogram buckets
# ---------------------------------------------------------------------------


class TestHistogramBuckets:
    def test_bucket_boundaries_present(self) -> None:
        mc = MetricsCollector("bucket_svc")
        mc.observe_request("/B", "OK", 0.001)  # fast
        mc.observe_request("/B", "OK", 5.0)  # slow

        # Check that the 0.005 bucket captured the fast request
        val_005 = _get_sample_value(
            "bucket_svc_grpc_request_duration_seconds_bucket",
            {"method": "/B", "le": "0.005"},
        )
        assert val_005 is not None and val_005 >= 1.0

        # The 10.0 bucket should have both
        val_10 = _get_sample_value(
            "bucket_svc_grpc_request_duration_seconds_bucket",
            {"method": "/B", "le": "10.0"},
        )
        assert val_10 is not None and val_10 >= 2.0


# ---------------------------------------------------------------------------
# active_requests counter
# ---------------------------------------------------------------------------


class TestActiveRequests:
    def test_active_requests_can_be_incremented(self) -> None:
        mc = MetricsCollector("active_svc")
        mc.active_requests.labels(method="/Stream").inc()

        val = _get_sample_value(
            "active_svc_grpc_active_requests_total",
            {"method": "/Stream"},
        )
        assert val is not None and val >= 1.0

    def test_active_requests_independent_per_method(self) -> None:
        mc = MetricsCollector("active_ind_svc")
        mc.active_requests.labels(method="/A").inc()
        mc.active_requests.labels(method="/A").inc()
        mc.active_requests.labels(method="/B").inc()

        val_a = _get_sample_value("active_ind_svc_grpc_active_requests_total", {"method": "/A"})
        val_b = _get_sample_value("active_ind_svc_grpc_active_requests_total", {"method": "/B"})
        assert val_a is not None and val_a >= 2.0
        assert val_b is not None and val_b >= 1.0


# ---------------------------------------------------------------------------
# start_metrics_server
# ---------------------------------------------------------------------------


class TestStartMetricsServerExtended:
    def test_thread_is_daemon(self) -> None:
        import threading

        initial_threads = {t.name for t in threading.enumerate()}

        with patch("pykit_metrics.prometheus.start_http_server"):
            start_metrics_server(19090)
            import time

            time.sleep(0.1)

        current_threads = threading.enumerate()
        metric_threads = [
            t for t in current_threads if t.name == "metrics-server" and t not in initial_threads
        ]
        # Thread should be daemon (won't block shutdown)
        for t in metric_threads:
            assert t.daemon

    def test_custom_port(self) -> None:
        with patch("pykit_metrics.prometheus.start_http_server") as mock_start:
            start_metrics_server(8888)
            import time

            time.sleep(0.1)
            mock_start.assert_called_once_with(8888)

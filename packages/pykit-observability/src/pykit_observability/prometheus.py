"""Prometheus metrics helpers for gRPC services."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from threading import Thread

from prometheus_client import (
    Counter,
    Histogram,
    generate_latest,
    start_http_server,
)


class MetricsCollector:
    """Standard metrics for a gRPC service."""

    def __init__(self, service_name: str = "pykit") -> None:
        self.service_name = service_name

        self.request_count = Counter(
            f"{service_name}_grpc_requests_total",
            "Total gRPC requests",
            ["method", "status"],
        )
        self.request_duration = Histogram(
            f"{service_name}_grpc_request_duration_seconds",
            "gRPC request duration in seconds",
            ["method"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
        )
        self.active_requests = Counter(
            f"{service_name}_grpc_active_requests",
            "Currently active gRPC requests",
            ["method"],
        )

    def observe_request(self, method: str, status: str, duration: float) -> None:
        """Record a completed gRPC request."""
        self.request_count.labels(method=method, status=status).inc()
        self.request_duration.labels(method=method).observe(duration)


class CounterMetric:
    """Labeled Prometheus counter owned by observability."""

    def __init__(self, name: str, documentation: str, labelnames: Iterable[str]) -> None:
        self._counter = Counter(name, documentation, list(labelnames))

    def inc(self, labels: Mapping[str, str], amount: float = 1.0) -> None:
        """Increment the counter for labels."""
        self._counter.labels(**labels).inc(amount)


class HistogramMetric:
    """Labeled Prometheus histogram owned by observability."""

    def __init__(self, name: str, documentation: str, labelnames: Iterable[str]) -> None:
        self._histogram = Histogram(name, documentation, list(labelnames))

    def observe(self, labels: Mapping[str, str], value: float) -> None:
        """Record value for labels."""
        self._histogram.labels(**labels).observe(value)


class MessageMetrics:
    """Standard Prometheus metrics for message consumers."""

    def __init__(self, prefix: str = "kafka_consumer") -> None:
        self.messages_total = CounterMetric(
            f"{prefix}_messages_total",
            "Total number of consumed messages",
            ["topic", "group"],
        )
        self.errors_total = CounterMetric(
            f"{prefix}_errors_total",
            "Total number of consumer errors",
            ["topic", "group"],
        )
        self.processing_duration = HistogramMetric(
            f"{prefix}_processing_duration_seconds",
            "Duration of message processing in seconds",
            ["topic", "group"],
        )

    def record(self, topic: str, group: str, duration: float, *, error: bool = False) -> None:
        """Record a message handling result."""
        labels = {"topic": topic, "group": group}
        self.messages_total.inc(labels)
        self.processing_duration.observe(labels, duration)
        if error:
            self.errors_total.inc(labels)


class HttpMetrics:
    """Standard Prometheus metrics for HTTP middleware."""

    def __init__(self) -> None:
        self.requests_total = CounterMetric(
            "http_requests_total",
            "Total number of HTTP requests",
            ["method", "path", "status_code"],
        )
        self.request_duration = HistogramMetric(
            "http_request_duration_seconds",
            "Duration of HTTP requests in seconds",
            ["method", "path", "status_code"],
        )
        self.request_size = HistogramMetric(
            "http_request_size_bytes",
            "Size of HTTP request bodies in bytes",
            ["method", "path"],
        )
        self.response_size = HistogramMetric(
            "http_response_size_bytes",
            "Size of HTTP response bodies in bytes",
            ["method", "path"],
        )

    def record_request_size(self, method: str, path: str, size: int) -> None:
        """Record HTTP request body size."""
        self.request_size.observe({"method": method, "path": path}, float(size))

    def record_response(
        self,
        method: str,
        path: str,
        status_code: int,
        duration: float,
        response_size: int,
    ) -> None:
        """Record completed HTTP response metrics."""
        labels = {"method": method, "path": path, "status_code": str(status_code)}
        self.requests_total.inc(labels)
        self.request_duration.observe(labels, duration)
        self.response_size.observe({"method": method, "path": path}, float(response_size))


def render_metrics() -> bytes:
    """Render the current Prometheus exposition payload."""
    return generate_latest()


def start_metrics_server(port: int = 9090) -> None:
    """Start the Prometheus metrics HTTP server in a background thread."""
    thread = Thread(
        target=start_http_server,
        args=(port,),
        daemon=True,
        name="metrics-server",
    )
    thread.start()

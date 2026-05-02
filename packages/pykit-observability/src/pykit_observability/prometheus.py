"""Prometheus metrics helpers for gRPC services."""

from __future__ import annotations

from threading import Thread

from prometheus_client import (
    Counter,
    Histogram,
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


def start_metrics_server(port: int = 9090) -> None:
    """Start the Prometheus metrics HTTP server in a background thread."""
    thread = Thread(
        target=start_http_server,
        args=(port,),
        daemon=True,
        name="metrics-server",
    )
    thread.start()

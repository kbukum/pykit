"""OpenTelemetry metrics setup and operation metrics."""

from __future__ import annotations

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource

from pykit_observability.config import MeterConfig


def setup_metrics(config: MeterConfig) -> MeterProvider:
    """Configure and set the global OTel meter provider."""
    resource = Resource.create({"service.name": config.service_name})
    provider = MeterProvider(resource=resource)
    metrics.set_meter_provider(provider)
    return provider


def get_meter(name: str) -> metrics.Meter:
    """Return a named meter from the global provider."""
    return metrics.get_meter(name)


class OperationMetrics:
    """Pre-built counter and histogram instruments for request/operation tracking."""

    def __init__(self, meter: metrics.Meter, prefix: str) -> None:
        self.request_counter = meter.create_counter(
            f"{prefix}.request.total",
            description="Total requests",
        )
        self.request_duration = meter.create_histogram(
            f"{prefix}.request.duration",
            description="Request duration in seconds",
            unit="s",
        )
        self.error_counter = meter.create_counter(
            f"{prefix}.error.total",
            description="Total errors",
        )

    def record_request(self, method: str, status: str, duration: float) -> None:
        """Record a completed request with method, status, and duration."""
        self.request_counter.add(1, {"method": method, "status": status})
        self.request_duration.record(duration, {"method": method, "status": status})
        if status == "error":
            self.error_counter.add(1, {"method": method})

"""OpenTelemetry metrics setup and operation metrics."""

from __future__ import annotations

import threading
from typing import Any

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.resources import Resource

from pykit_observability.config import MeterConfig

_setup_lock = threading.Lock()
_meter_provider: Any = None


def setup_metrics(config: MeterConfig) -> MeterProvider:
    """Configure and set the global OTel meter provider. Idempotent — safe to call multiple times."""
    global _meter_provider
    with _setup_lock:
        if _meter_provider is not None:
            return _meter_provider
        resource = Resource.create({"service.name": config.service_name})
        provider = MeterProvider(resource=resource)
        metrics.set_meter_provider(provider)
        _meter_provider = provider
        return provider


def reset_metrics() -> None:
    """Reset to NoOp provider. Intended for test teardown only."""
    global _meter_provider
    with _setup_lock:
        metrics.set_meter_provider(metrics.ProxyMeterProvider())
        _meter_provider = None


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

"""pykit_observability — OpenTelemetry tracing and metrics integration."""

from __future__ import annotations

from pykit_observability.config import MeterConfig, TracerConfig
from pykit_observability.context import OperationContext
from pykit_observability.exporters import (
    OtlpExporterConfig,
    create_metric_exporter,
    create_span_exporter,
    setup_otlp_metrics,
    setup_otlp_tracing,
)
from pykit_observability.health import ComponentHealth, HealthStatus, ServiceHealth
from pykit_observability.metrics import OperationMetrics, get_meter, setup_metrics
from pykit_observability.tracing import get_tracer, setup_tracing, trace_operation

__all__ = [
    "ComponentHealth",
    "HealthStatus",
    "MeterConfig",
    "OperationContext",
    "OperationMetrics",
    "OtlpExporterConfig",
    "ServiceHealth",
    "TracerConfig",
    "create_metric_exporter",
    "create_span_exporter",
    "get_meter",
    "get_tracer",
    "setup_metrics",
    "setup_otlp_metrics",
    "setup_otlp_tracing",
    "setup_tracing",
    "trace_operation",
]

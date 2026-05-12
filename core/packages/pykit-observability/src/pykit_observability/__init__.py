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
from pykit_observability.metrics import OperationMetrics, get_meter, reset_metrics, setup_metrics
from pykit_observability.prometheus import (
    CounterMetric,
    HistogramMetric,
    HttpMetrics,
    MessageMetrics,
    MetricsCollector,
    render_metrics,
    start_metrics_server,
)
from pykit_observability.propagation import (
    MappingCarrier,
    TextMapCarrier,
    TraceContext,
    extract_trace_context,
    inject_trace_context,
)
from pykit_observability.span import Span, SpanKind, start_span
from pykit_observability.tracing import get_tracer, reset_tracing, setup_tracing, trace_operation

__all__ = [
    "ComponentHealth",
    "CounterMetric",
    "HistogramMetric",
    "HealthStatus",
    "HttpMetrics",
    "MeterConfig",
    "MessageMetrics",
    "MetricsCollector",
    "MappingCarrier",
    "OperationContext",
    "OperationMetrics",
    "OtlpExporterConfig",
    "ServiceHealth",
    "Span",
    "SpanKind",
    "TextMapCarrier",
    "TraceContext",
    "TracerConfig",
    "create_metric_exporter",
    "create_span_exporter",
    "extract_trace_context",
    "get_meter",
    "get_tracer",
    "inject_trace_context",
    "reset_metrics",
    "reset_tracing",
    "render_metrics",
    "setup_metrics",
    "setup_otlp_metrics",
    "setup_otlp_tracing",
    "setup_tracing",
    "start_span",
    "start_metrics_server",
    "trace_operation",
]

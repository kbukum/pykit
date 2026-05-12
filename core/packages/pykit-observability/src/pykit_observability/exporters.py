"""OTLP HTTP/JSON exporters for OpenTelemetry (avoids gRPC protobuf conflicts)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SpanExporter

try:
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    OTLP_HTTP_AVAILABLE = True
except ImportError:
    OTLP_HTTP_AVAILABLE = False


@dataclass
class OtlpExporterConfig:
    """Configuration for OTLP HTTP/JSON exporters."""

    endpoint: str = "http://localhost:4318"
    """OTLP HTTP endpoint (e.g., http://localhost:4318)."""

    protocol: str = "http/json"
    """Protocol: 'http/json' or 'http/protobuf'. Default is 'http/json'."""

    headers: dict[str, str] | None = None
    """Custom HTTP headers to include in exporter requests."""

    timeout: float = 10.0
    """Request timeout in seconds."""

    compression: str | None = None
    """Compression type: 'gzip' or None for no compression."""

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.protocol not in ("http/json", "http/protobuf"):
            msg = f"protocol must be 'http/json' or 'http/protobuf', got {self.protocol!r}"
            raise ValueError(msg)
        if self.timeout <= 0:
            msg = "timeout must be positive"
            raise ValueError(msg)
        if self.compression and self.compression not in ("gzip",):
            msg = f"compression must be 'gzip' or None, got {self.compression!r}"
            raise ValueError(msg)


def create_span_exporter(config: OtlpExporterConfig) -> SpanExporter:
    """Create an OTLP span exporter with HTTP transport.

    Args:
        config: OtlpExporterConfig with endpoint, headers, timeout, etc.

    Returns:
        OTLPSpanExporter configured for HTTP/JSON protocol.

    Raises:
        ImportError: If opentelemetry-exporter-otlp-proto-http is not installed.
    """
    if not OTLP_HTTP_AVAILABLE:
        msg = (
            "opentelemetry-exporter-otlp-proto-http is not installed. "
            "Install it with: pip install opentelemetry-exporter-otlp-proto-http"
        )
        raise ImportError(msg)

    kwargs: dict[str, Any] = {
        "endpoint": config.endpoint,
        "timeout": int(config.timeout * 1000),  # Convert to milliseconds
    }

    if config.headers:
        kwargs["headers"] = config.headers

    if config.compression:
        from opentelemetry.exporter.otlp.proto.http import Compression

        kwargs["compression"] = Compression.Gzip

    # http/json is default for OTLPSpanExporter; no explicit protocol param needed
    return OTLPSpanExporter(**kwargs)


def create_metric_exporter(config: OtlpExporterConfig) -> MetricExporter:
    """Create an OTLP metric exporter with HTTP transport.

    Args:
        config: OtlpExporterConfig with endpoint, headers, timeout, etc.

    Returns:
        OTLPMetricExporter configured for HTTP/JSON protocol.

    Raises:
        ImportError: If opentelemetry-exporter-otlp-proto-http is not installed.
    """
    if not OTLP_HTTP_AVAILABLE:
        msg = (
            "opentelemetry-exporter-otlp-proto-http is not installed. "
            "Install it with: pip install opentelemetry-exporter-otlp-proto-http"
        )
        raise ImportError(msg)

    kwargs: dict[str, Any] = {
        "endpoint": config.endpoint,
        "timeout": int(config.timeout * 1000),  # Convert to milliseconds
    }

    if config.headers:
        kwargs["headers"] = config.headers

    if config.compression:
        from opentelemetry.exporter.otlp.proto.http import Compression

        kwargs["compression"] = Compression.Gzip

    return OTLPMetricExporter(**kwargs)


def setup_otlp_tracing(
    service_name: str,
    config: OtlpExporterConfig | None = None,
) -> TracerProvider:
    """Setup OTLP tracing with HTTP exporter as the global tracer provider.

    Creates a TracerProvider with a BatchSpanProcessor that exports spans
    to an OTLP HTTP endpoint. Sets this as the global tracer provider.

    The returned provider owns a background ``BatchSpanProcessor`` thread.
    Callers MUST call ``provider.shutdown()`` during application teardown
    (or use it inside a context manager) to stop the exporter thread; otherwise
    the process may hang waiting on retry/flush attempts.

    Args:
        service_name: Service name for resource attribution.
        config: OtlpExporterConfig. If None, uses defaults.

    Returns:
        Configured TracerProvider (also set as global). Caller owns shutdown.

    Raises:
        ImportError: If opentelemetry-exporter-otlp-proto-http is not installed.
    """
    if config is None:
        config = OtlpExporterConfig()

    resource = Resource.create({"service.name": service_name})
    exporter = create_span_exporter(config)
    processor = BatchSpanProcessor(exporter)

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(processor)

    from opentelemetry import trace

    trace.set_tracer_provider(provider)
    return provider


def setup_otlp_metrics(
    service_name: str,
    config: OtlpExporterConfig | None = None,
) -> MeterProvider:
    """Setup OTLP metrics with HTTP exporter as the global meter provider.

    Creates a MeterProvider with a PeriodicExportingMetricReader that exports
    metrics to an OTLP HTTP endpoint. Sets this as the global meter provider.

    The returned provider owns a background ``PeriodicExportingMetricReader``
    thread. Callers MUST call ``provider.shutdown()`` during application
    teardown to stop the exporter thread; otherwise the process may hang
    waiting on retry/flush attempts after the test or app exits.

    Args:
        service_name: Service name for resource attribution.
        config: OtlpExporterConfig. If None, uses defaults.

    Returns:
        Configured MeterProvider (also set as global). Caller owns shutdown.

    Raises:
        ImportError: If opentelemetry-exporter-otlp-proto-http is not installed.
    """
    if config is None:
        config = OtlpExporterConfig()

    resource = Resource.create({"service.name": service_name})
    exporter = create_metric_exporter(config)
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=60000)

    provider = MeterProvider(resource=resource, metric_readers=[reader])

    from opentelemetry import metrics

    metrics.set_meter_provider(provider)
    return provider

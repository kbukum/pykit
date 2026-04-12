"""Tests for OTLP HTTP/JSON exporters."""

from __future__ import annotations

import pytest

from pykit_observability.exporters import (
    OTLP_HTTP_AVAILABLE,
    OtlpExporterConfig,
    create_metric_exporter,
    create_span_exporter,
    setup_otlp_metrics,
    setup_otlp_tracing,
)


class TestOtlpExporterConfig:
    """Tests for OtlpExporterConfig dataclass."""

    def test_defaults(self) -> None:
        """Test default configuration values."""
        config = OtlpExporterConfig()
        assert config.endpoint == "http://localhost:4318"
        assert config.protocol == "http/json"
        assert config.headers is None
        assert config.timeout == 10.0
        assert config.compression is None

    def test_custom_endpoint(self) -> None:
        """Test custom endpoint configuration."""
        config = OtlpExporterConfig(endpoint="http://otel-collector:4318")
        assert config.endpoint == "http://otel-collector:4318"

    def test_custom_headers(self) -> None:
        """Test custom headers configuration."""
        headers = {"Authorization": "Bearer token123"}
        config = OtlpExporterConfig(headers=headers)
        assert config.headers == headers

    def test_custom_timeout(self) -> None:
        """Test custom timeout configuration."""
        config = OtlpExporterConfig(timeout=20.0)
        assert config.timeout == 20.0

    def test_compression_gzip(self) -> None:
        """Test gzip compression configuration."""
        config = OtlpExporterConfig(compression="gzip")
        assert config.compression == "gzip"

    def test_invalid_protocol(self) -> None:
        """Test validation of invalid protocol."""
        with pytest.raises(ValueError, match="protocol must be"):
            OtlpExporterConfig(protocol="grpc")

    def test_invalid_timeout_zero(self) -> None:
        """Test validation of zero timeout."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            OtlpExporterConfig(timeout=0.0)

    def test_invalid_timeout_negative(self) -> None:
        """Test validation of negative timeout."""
        with pytest.raises(ValueError, match="timeout must be positive"):
            OtlpExporterConfig(timeout=-5.0)

    def test_invalid_compression(self) -> None:
        """Test validation of invalid compression type."""
        with pytest.raises(ValueError, match="compression must be"):
            OtlpExporterConfig(compression="deflate")


@pytest.mark.skipif(not OTLP_HTTP_AVAILABLE, reason="opentelemetry-exporter-otlp-proto-http not installed")
class TestCreateSpanExporter:
    """Tests for create_span_exporter function."""

    def test_create_span_exporter_default(self) -> None:
        """Test creating span exporter with default config."""
        exporter = create_span_exporter(OtlpExporterConfig())
        assert exporter is not None
        assert hasattr(exporter, "export")
        assert hasattr(exporter, "shutdown")

    def test_create_span_exporter_custom_endpoint(self) -> None:
        """Test creating span exporter with custom endpoint."""
        config = OtlpExporterConfig(endpoint="http://custom-collector:4318")
        exporter = create_span_exporter(config)
        assert exporter is not None

    def test_create_span_exporter_with_headers(self) -> None:
        """Test creating span exporter with custom headers."""
        headers = {"X-Custom-Header": "value"}
        config = OtlpExporterConfig(headers=headers)
        exporter = create_span_exporter(config)
        assert exporter is not None

    def test_create_span_exporter_with_timeout(self) -> None:
        """Test creating span exporter with custom timeout."""
        config = OtlpExporterConfig(timeout=20.0)
        exporter = create_span_exporter(config)
        assert exporter is not None

    def test_create_span_exporter_with_gzip(self) -> None:
        """Test creating span exporter with gzip compression."""
        config = OtlpExporterConfig(compression="gzip")
        exporter = create_span_exporter(config)
        assert exporter is not None


@pytest.mark.skipif(not OTLP_HTTP_AVAILABLE, reason="opentelemetry-exporter-otlp-proto-http not installed")
class TestCreateMetricExporter:
    """Tests for create_metric_exporter function."""

    def test_create_metric_exporter_default(self) -> None:
        """Test creating metric exporter with default config."""
        exporter = create_metric_exporter(OtlpExporterConfig())
        assert exporter is not None
        assert hasattr(exporter, "export")
        assert hasattr(exporter, "shutdown")

    def test_create_metric_exporter_custom_endpoint(self) -> None:
        """Test creating metric exporter with custom endpoint."""
        config = OtlpExporterConfig(endpoint="http://custom-collector:4318")
        exporter = create_metric_exporter(config)
        assert exporter is not None

    def test_create_metric_exporter_with_headers(self) -> None:
        """Test creating metric exporter with custom headers."""
        headers = {"X-Custom-Header": "value"}
        config = OtlpExporterConfig(headers=headers)
        exporter = create_metric_exporter(config)
        assert exporter is not None

    def test_create_metric_exporter_with_timeout(self) -> None:
        """Test creating metric exporter with custom timeout."""
        config = OtlpExporterConfig(timeout=20.0)
        exporter = create_metric_exporter(config)
        assert exporter is not None

    def test_create_metric_exporter_with_gzip(self) -> None:
        """Test creating metric exporter with gzip compression."""
        config = OtlpExporterConfig(compression="gzip")
        exporter = create_metric_exporter(config)
        assert exporter is not None


@pytest.mark.skipif(not OTLP_HTTP_AVAILABLE, reason="opentelemetry-exporter-otlp-proto-http not installed")
class TestSetupOtlpTracing:
    """Tests for setup_otlp_tracing function."""

    def test_setup_otlp_tracing_default(self) -> None:
        """Test setup_otlp_tracing with default config."""
        provider = setup_otlp_tracing("test-service")
        assert provider is not None
        assert hasattr(provider, "add_span_processor")
        assert hasattr(provider, "get_tracer")

    def test_setup_otlp_tracing_custom_config(self) -> None:
        """Test setup_otlp_tracing with custom config."""
        config = OtlpExporterConfig(
            endpoint="http://otel-collector:4318",
            timeout=15.0,
        )
        provider = setup_otlp_tracing("test-service", config)
        assert provider is not None

    def test_setup_otlp_tracing_sets_global_provider(self) -> None:
        """Test that setup_otlp_tracing sets global provider."""
        from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider

        provider = setup_otlp_tracing("test-service-global")
        assert isinstance(provider, SDKTracerProvider)

    def test_setup_otlp_tracing_returns_tracer_provider(self) -> None:
        """Test that setup_otlp_tracing returns a valid TracerProvider."""
        from opentelemetry.sdk.trace import TracerProvider as SDKTracerProvider

        provider = setup_otlp_tracing("test-service-type")
        assert isinstance(provider, SDKTracerProvider)


@pytest.mark.skipif(not OTLP_HTTP_AVAILABLE, reason="opentelemetry-exporter-otlp-proto-http not installed")
class TestSetupOtlpMetrics:
    """Tests for setup_otlp_metrics function."""

    def test_setup_otlp_metrics_default(self) -> None:
        """Test setup_otlp_metrics with default config."""
        provider = setup_otlp_metrics("test-service")
        assert provider is not None
        assert hasattr(provider, "get_meter")

    def test_setup_otlp_metrics_custom_config(self) -> None:
        """Test setup_otlp_metrics with custom config."""
        config = OtlpExporterConfig(
            endpoint="http://otel-collector:4318",
            timeout=15.0,
        )
        provider = setup_otlp_metrics("test-service", config)
        assert provider is not None

    def test_setup_otlp_metrics_sets_global_provider(self) -> None:
        """Test that setup_otlp_metrics sets global provider."""
        from opentelemetry.sdk.metrics import MeterProvider as SDKMeterProvider

        provider = setup_otlp_metrics("test-service-global")
        assert isinstance(provider, SDKMeterProvider)

    def test_setup_otlp_metrics_returns_meter_provider(self) -> None:
        """Test that setup_otlp_metrics returns a valid MeterProvider."""
        from opentelemetry.sdk.metrics import MeterProvider as SDKMeterProvider

        provider = setup_otlp_metrics("test-service-type")
        assert isinstance(provider, SDKMeterProvider)


class TestMissingDependency:
    """Tests for handling missing opentelemetry-exporter-otlp-proto-http."""

    @pytest.mark.skipif(OTLP_HTTP_AVAILABLE, reason="opentelemetry-exporter-otlp-proto-http is installed")
    def test_create_span_exporter_missing_dependency(self) -> None:
        """Test that ImportError is raised when dependency is missing."""
        with pytest.raises(ImportError, match="opentelemetry-exporter-otlp-proto-http is not installed"):
            create_span_exporter(OtlpExporterConfig())

    @pytest.mark.skipif(OTLP_HTTP_AVAILABLE, reason="opentelemetry-exporter-otlp-proto-http is installed")
    def test_create_metric_exporter_missing_dependency(self) -> None:
        """Test that ImportError is raised when dependency is missing."""
        with pytest.raises(ImportError, match="opentelemetry-exporter-otlp-proto-http is not installed"):
            create_metric_exporter(OtlpExporterConfig())

    @pytest.mark.skipif(OTLP_HTTP_AVAILABLE, reason="opentelemetry-exporter-otlp-proto-http is installed")
    def test_setup_otlp_tracing_missing_dependency(self) -> None:
        """Test that ImportError is raised when dependency is missing."""
        with pytest.raises(ImportError, match="opentelemetry-exporter-otlp-proto-http is not installed"):
            setup_otlp_tracing("test-service")

    @pytest.mark.skipif(OTLP_HTTP_AVAILABLE, reason="opentelemetry-exporter-otlp-proto-http is installed")
    def test_setup_otlp_metrics_missing_dependency(self) -> None:
        """Test that ImportError is raised when dependency is missing."""
        with pytest.raises(ImportError, match="opentelemetry-exporter-otlp-proto-http is not installed"):
            setup_otlp_metrics("test-service")

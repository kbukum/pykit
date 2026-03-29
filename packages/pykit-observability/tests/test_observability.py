"""Tests for pykit_observability."""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pykit_observability import (
    MeterConfig,
    OperationContext,
    OperationMetrics,
    TracerConfig,
    get_meter,
    get_tracer,
    setup_metrics,
    setup_tracing,
    trace_operation,
)


def _reset_tracer_provider() -> None:
    """Reset the global OTel tracer provider so tests can set their own."""
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False


@pytest.fixture(autouse=True)
def _reset_otel() -> None:
    """Reset global OTel state before each test."""
    _reset_tracer_provider()


# -- Config defaults -----------------------------------------------------------


class TestTracerConfig:
    def test_defaults(self) -> None:
        cfg = TracerConfig(service_name="svc")
        assert cfg.service_name == "svc"
        assert cfg.endpoint == ""
        assert cfg.sample_rate == 1.0
        assert cfg.enabled is True


class TestMeterConfig:
    def test_defaults(self) -> None:
        cfg = MeterConfig(service_name="svc")
        assert cfg.service_name == "svc"
        assert cfg.endpoint == ""
        assert cfg.export_interval == 60.0
        assert cfg.enabled is True


# -- Tracing -------------------------------------------------------------------


class TestSetupTracing:
    def test_creates_provider(self) -> None:
        cfg = TracerConfig(service_name="test-svc")
        provider = setup_tracing(cfg)
        assert isinstance(provider, TracerProvider)

    def test_get_tracer_returns_tracer(self) -> None:
        setup_tracing(TracerConfig(service_name="test-svc"))
        tracer = get_tracer("my-tracer")
        assert tracer is not None


class TestTraceOperation:
    @pytest.fixture(autouse=True)
    def _setup_provider(self) -> None:
        self.exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        trace.set_tracer_provider(provider)

    async def test_creates_span(self) -> None:
        async with trace_operation("test.op", attributes={"key": "val"}) as span:
            assert span.is_recording()

        spans = self.exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test.op"
        assert spans[0].attributes is not None
        assert spans[0].attributes.get("key") == "val"


# -- Metrics -------------------------------------------------------------------


class TestOperationMetrics:
    def test_record_request(self) -> None:
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": "test-svc"})
        provider = MeterProvider(resource=resource)
        meter = provider.get_meter("test-meter")
        om = OperationMetrics(meter, "myapp")
        om.record_request("GET", "ok", 0.123)
        om.record_request("POST", "error", 0.456)
        provider.shutdown()

    def test_setup_metrics_creates_provider(self) -> None:
        from opentelemetry.sdk.metrics import MeterProvider

        provider = setup_metrics(MeterConfig(service_name="test-svc"))
        assert isinstance(provider, MeterProvider)
        meter = get_meter("test-meter")
        assert meter is not None
        provider.shutdown()


# -- OperationContext ----------------------------------------------------------


class TestOperationContext:
    @pytest.fixture(autouse=True)
    def _setup_provider(self) -> None:
        self.exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(self.exporter))
        trace.set_tracer_provider(provider)

    async def test_context_manager(self) -> None:
        ctx = OperationContext("test.ctx", attributes={"a": "b"})
        async with ctx():
            ctx.set_attribute("extra", "value")
            assert ctx.span.is_recording()

        spans = self.exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "test.ctx"

    async def test_record_error(self) -> None:
        ctx = OperationContext("fail.op")
        with pytest.raises(ValueError, match="boom"):
            async with ctx():
                raise ValueError("boom")

        spans = self.exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR

    def test_span_outside_context(self) -> None:
        ctx = OperationContext("no.span")
        assert ctx.span is trace.INVALID_SPAN

    async def test_elapsed(self) -> None:
        ctx = OperationContext("timed.op")
        async with ctx():
            assert ctx.elapsed > 0.0

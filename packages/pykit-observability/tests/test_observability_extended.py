"""Extended tests for pykit_observability — fills coverage gaps."""

from __future__ import annotations

import threading
import time

import pytest
from opentelemetry import trace
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import InMemoryMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pykit_observability import (
    ComponentHealth,
    HealthStatus,
    MeterConfig,
    OperationContext,
    OperationMetrics,
    ServiceHealth,
    TracerConfig,
    get_meter,
    get_tracer,
    setup_metrics,
    setup_tracing,
)


def _reset_tracer_provider() -> None:
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False


def _reset_meter_provider() -> None:
    from opentelemetry.metrics import _internal

    _internal._METER_PROVIDER = None
    _internal._METER_PROVIDER_SET_ONCE._done = False


@pytest.fixture(autouse=True)
def _reset_otel() -> None:
    _reset_tracer_provider()
    _reset_meter_provider()


# ── ServiceHealth full test suite ────────────────────────────────────────────


class TestServiceHealthRegister:
    def test_register_single(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("db")
        status = sh.status()
        assert "db" in status
        assert status["db"].status == HealthStatus.HEALTHY

    def test_register_multiple(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("db")
        sh.register("cache")
        sh.register("queue")
        assert len(sh.status()) == 3

    def test_service_version(self) -> None:
        sh = ServiceHealth("my-svc", "2.1.0")
        assert sh.service == "my-svc"
        assert sh.version == "2.1.0"


class TestServiceHealthUpdate:
    def test_update_to_degraded(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("db")
        sh.update("db", HealthStatus.DEGRADED, "slow queries")
        status = sh.status()
        assert status["db"].status == HealthStatus.DEGRADED
        assert status["db"].message == "slow queries"

    def test_update_to_unhealthy(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("cache")
        sh.update("cache", HealthStatus.UNHEALTHY, "connection refused")
        assert not sh.is_healthy()

    def test_update_back_to_healthy(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("db")
        sh.update("db", HealthStatus.UNHEALTHY, "down")
        sh.update("db", HealthStatus.HEALTHY, "recovered")
        assert sh.is_healthy()


class TestServiceHealthIsHealthy:
    def test_all_healthy(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("a")
        sh.register("b")
        assert sh.is_healthy()

    def test_one_degraded(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("a")
        sh.register("b")
        sh.update("b", HealthStatus.DEGRADED)
        assert not sh.is_healthy()

    def test_empty_is_healthy(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        assert sh.is_healthy()


class TestServiceHealthOverallStatus:
    def test_all_healthy(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("a")
        sh.register("b")
        assert sh.overall_status() == HealthStatus.HEALTHY

    def test_one_degraded(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("a")
        sh.update("a", HealthStatus.DEGRADED)
        assert sh.overall_status() == HealthStatus.DEGRADED

    def test_one_unhealthy(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("a")
        sh.register("b")
        sh.update("a", HealthStatus.UNHEALTHY)
        assert sh.overall_status() == HealthStatus.UNHEALTHY

    def test_unhealthy_trumps_degraded(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        sh.register("a")
        sh.register("b")
        sh.update("a", HealthStatus.DEGRADED)
        sh.update("b", HealthStatus.UNHEALTHY)
        assert sh.overall_status() == HealthStatus.UNHEALTHY

    def test_empty_returns_healthy(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        assert sh.overall_status() == HealthStatus.HEALTHY


# ── ServiceHealth concurrent updates ─────────────────────────────────────────


class TestServiceHealthConcurrency:
    def test_concurrent_register_and_update(self) -> None:
        sh = ServiceHealth("svc", "1.0")
        errors: list[Exception] = []

        def worker(component_id: int) -> None:
            try:
                name = f"comp-{component_id}"
                sh.register(name)
                sh.update(name, HealthStatus.DEGRADED, "test")
                sh.update(name, HealthStatus.HEALTHY)
                _ = sh.is_healthy()
                _ = sh.overall_status()
                _ = sh.status()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"Errors during concurrent access: {errors}"
        assert len(sh.status()) == 20


# ── ComponentHealth dataclass ────────────────────────────────────────────────


class TestComponentHealth:
    def test_construction(self) -> None:
        ch = ComponentHealth(name="db", status=HealthStatus.HEALTHY)
        assert ch.name == "db"
        assert ch.status == HealthStatus.HEALTHY
        assert ch.message == ""

    def test_with_message(self) -> None:
        ch = ComponentHealth(name="cache", status=HealthStatus.DEGRADED, message="slow")
        assert ch.message == "slow"

    def test_frozen_immutability(self) -> None:
        ch = ComponentHealth(name="db", status=HealthStatus.HEALTHY)
        with pytest.raises(AttributeError):
            ch.name = "other"  # type: ignore[misc]

    def test_frozen_status_immutability(self) -> None:
        ch = ComponentHealth(name="db", status=HealthStatus.HEALTHY)
        with pytest.raises(AttributeError):
            ch.status = HealthStatus.UNHEALTHY  # type: ignore[misc]


# ── HealthStatus enum ────────────────────────────────────────────────────────


class TestHealthStatus:
    def test_values(self) -> None:
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED == "degraded"
        assert HealthStatus.UNHEALTHY == "unhealthy"

    def test_string_comparison(self) -> None:
        assert HealthStatus.HEALTHY == "healthy"
        assert HealthStatus.DEGRADED != "healthy"

    def test_is_str_subclass(self) -> None:
        assert isinstance(HealthStatus.HEALTHY, str)


# ── OperationMetrics error counter ───────────────────────────────────────────


class TestOperationMetricsErrorCounter:
    def _make_metrics(self) -> tuple[OperationMetrics, InMemoryMetricReader]:
        reader = InMemoryMetricReader()
        resource = Resource.create({"service.name": "test-svc"})
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        meter = provider.get_meter("test-meter")
        return OperationMetrics(meter, "myapp"), reader

    def test_error_status_increments_error_counter(self) -> None:
        om, reader = self._make_metrics()
        om.record_request("POST", "error", 0.1)
        data = reader.get_metrics_data()
        names = [m.name for rm in data.resource_metrics for sm in rm.scope_metrics for m in sm.metrics]
        assert "myapp.error.total" in names

    def test_ok_status_does_not_increment_error_counter(self) -> None:
        om, reader = self._make_metrics()
        om.record_request("GET", "ok", 0.05)
        data = reader.get_metrics_data()
        # error counter should either not be present or have 0
        for rm in data.resource_metrics:
            for sm in rm.scope_metrics:
                for m in sm.metrics:
                    if m.name == "myapp.error.total":
                        for dp in m.data.data_points:
                            assert dp.value == 0


class TestOperationMetricsAttributes:
    def test_request_attributes(self) -> None:
        reader = InMemoryMetricReader()
        resource = Resource.create({"service.name": "test-svc"})
        provider = MeterProvider(resource=resource, metric_readers=[reader])
        meter = provider.get_meter("test-meter")
        om = OperationMetrics(meter, "app")
        om.record_request("GET", "ok", 0.123)

        data = reader.get_metrics_data()
        for rm in data.resource_metrics:
            for sm in rm.scope_metrics:
                for m in sm.metrics:
                    if m.name == "app.request.total":
                        for dp in m.data.data_points:
                            attrs = dict(dp.attributes)
                            assert attrs["method"] == "GET"
                            assert attrs["status"] == "ok"


# ── Sampling behavior ────────────────────────────────────────────────────────


class TestSamplingBehavior:
    def test_always_on(self) -> None:
        exporter = InMemorySpanExporter()
        provider = setup_tracing(TracerConfig(service_name="svc", sample_rate=1.0))
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("sampled"):
            pass
        assert len(exporter.get_finished_spans()) == 1
        provider.shutdown()

    def test_always_off(self) -> None:
        from opentelemetry.sdk.trace import TracerProvider as SdkProvider
        from opentelemetry.sdk.trace.sampling import ALWAYS_OFF

        provider = SdkProvider(sampler=ALWAYS_OFF)
        exporter = InMemorySpanExporter()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        tracer = provider.get_tracer("test")
        with tracer.start_as_current_span("not-sampled"):
            pass
        assert len(exporter.get_finished_spans()) == 0
        provider.shutdown()


# ── Trace context propagation ────────────────────────────────────────────────


class TestTraceContextPropagation:
    def test_span_context_in_headers(self) -> None:
        from opentelemetry.propagate import inject

        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        tracer = trace.get_tracer("test")
        with tracer.start_as_current_span("propagated"):
            headers: dict[str, str] = {}
            inject(headers)
            assert "traceparent" in headers


# ── OperationContext elapsed accuracy ────────────────────────────────────────


class TestOperationContextElapsed:
    async def test_elapsed_grows(self) -> None:
        ctx = OperationContext("timed.op")
        async with ctx():
            t1 = ctx.elapsed
            time.sleep(0.02)
            t2 = ctx.elapsed
            assert t2 > t1

    def test_elapsed_zero_outside_context(self) -> None:
        ctx = OperationContext("no-context")
        assert ctx.elapsed == 0.0

    async def test_elapsed_positive_in_context(self) -> None:
        ctx = OperationContext("timed")
        async with ctx():
            assert ctx.elapsed >= 0.0


# ── Multiple OperationContext instances ──────────────────────────────────────


class TestMultipleOperationContexts:
    async def test_independent_contexts(self) -> None:
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        ctx1 = OperationContext("op1", attributes={"key": "val1"})
        ctx2 = OperationContext("op2", attributes={"key": "val2"})

        async with ctx1():
            pass
        async with ctx2():
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 2
        names = {s.name for s in spans}
        assert "op1" in names
        assert "op2" in names

    async def test_nested_contexts(self) -> None:
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        outer = OperationContext("outer")
        inner = OperationContext("inner")

        async with outer(), inner():
            pass

        spans = exporter.get_finished_spans()
        assert len(spans) == 2

    async def test_context_error_propagation(self) -> None:
        exporter = InMemorySpanExporter()
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)

        ctx = OperationContext("error.op")
        with pytest.raises(RuntimeError, match="test error"):
            async with ctx():
                raise RuntimeError("test error")

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR


# ── Setup functions ──────────────────────────────────────────────────────────


class TestSetupFunctions:
    def test_setup_metrics_returns_provider(self) -> None:
        provider = setup_metrics(MeterConfig(service_name="svc"))
        assert isinstance(provider, MeterProvider)
        provider.shutdown()

    def test_get_meter_returns_meter(self) -> None:
        provider = setup_metrics(MeterConfig(service_name="svc"))
        meter = get_meter("test-meter")
        assert meter is not None
        provider.shutdown()

    def test_setup_tracing_returns_provider(self) -> None:
        provider = setup_tracing(TracerConfig(service_name="svc"))
        assert isinstance(provider, TracerProvider)
        provider.shutdown()

    def test_get_tracer_returns_tracer(self) -> None:
        setup_tracing(TracerConfig(service_name="svc"))
        tracer = get_tracer("test-tracer")
        assert tracer is not None

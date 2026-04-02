"""Tests for Kafka tracing middleware."""

from __future__ import annotations

import pytest

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pykit_kafka.types import Message
from pykit_kafka_middleware.tracing import TracingHandler, extract_trace_context, inject_trace_context


@pytest.fixture(autouse=True)
def _setup_tracer():
    """Set up an in-memory tracer for test assertions."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    # Reset the global tracer provider for test isolation.
    trace._TRACER_PROVIDER = None  # noqa: SLF001
    trace._TRACER_PROVIDER_SET_ONCE._done = False  # noqa: SLF001
    trace.set_tracer_provider(provider)

    yield exporter

    provider.shutdown()


def _make_msg(topic: str = "test-topic") -> Message:
    return Message(key="k1", value=b"data", topic=topic, partition=0, offset=0, headers={})


class TestTracingHandler:
    async def test_creates_span(self, _setup_tracer: InMemorySpanExporter) -> None:
        exporter = _setup_tracer
        called = False

        async def handler(msg: Message) -> None:
            nonlocal called
            called = True

        wrapped = TracingHandler(handler)
        await wrapped(_make_msg(topic="orders"))

        assert called
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == "orders consume"
        assert spans[0].kind == trace.SpanKind.CONSUMER

        attrs = dict(spans[0].attributes or {})
        assert attrs["messaging.system"] == "kafka"
        assert attrs["messaging.destination"] == "orders"

    async def test_records_error(self, _setup_tracer: InMemorySpanExporter) -> None:
        exporter = _setup_tracer

        async def handler(msg: Message) -> None:
            raise RuntimeError("process error")

        wrapped = TracingHandler(handler)

        with pytest.raises(RuntimeError, match="process error"):
            await wrapped(_make_msg())

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR

    async def test_custom_span_name(self, _setup_tracer: InMemorySpanExporter) -> None:
        exporter = _setup_tracer

        async def handler(msg: Message) -> None:
            pass

        wrapped = TracingHandler(
            handler,
            span_name_func=lambda msg: f"custom-{msg.topic}",
        )
        await wrapped(_make_msg(topic="events"))

        spans = exporter.get_finished_spans()
        assert spans[0].name == "custom-events"


class TestTraceContextPropagation:
    def test_inject_and_extract_roundtrip(self) -> None:
        headers: dict[str, str] = {}
        inject_trace_context(headers)
        ctx = extract_trace_context(headers)
        assert ctx is not None

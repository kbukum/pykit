"""Tests for HTTP tracing middleware."""

from __future__ import annotations

import pytest

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from pykit_server_middleware.tracing import TracingMiddleware


@pytest.fixture(autouse=True)
def setup_tracer():
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


def _make_scope(
    method: str = "GET",
    path: str = "/api/test",
    scheme: str = "http",
) -> dict:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "scheme": scheme,
        "headers": [],
    }


async def _simple_app(scope, receive, send):
    """Minimal ASGI app that returns 200."""
    await send({
        "type": "http.response.start",
        "status": 200,
        "headers": [(b"content-type", b"text/plain")],
    })
    await send({
        "type": "http.response.body",
        "body": b"OK",
    })


async def _error_app(scope, receive, send):
    """ASGI app that returns 500."""
    await send({
        "type": "http.response.start",
        "status": 500,
        "headers": [],
    })
    await send({"type": "http.response.body", "body": b"Error"})


async def _receive():
    return {"type": "http.request", "body": b""}


class TestTracingMiddleware:
    async def test_creates_span_with_attributes(self, setup_tracer) -> None:
        exporter = setup_tracer
        app = TracingMiddleware(_simple_app)

        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        await app(_make_scope(method="POST", path="/users"), _receive, send)

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.name == "POST /users"
        assert span.kind == trace.SpanKind.SERVER

        attrs = dict(span.attributes or {})
        assert attrs["http.method"] == "POST"
        assert attrs["http.target"] == "/users"
        assert attrs["http.scheme"] == "http"
        assert attrs["http.status_code"] == 200

    async def test_marks_5xx_as_error(self, setup_tracer) -> None:
        exporter = setup_tracer
        app = TracingMiddleware(_error_app)

        sent: list[dict] = []
        await app(_make_scope(), _receive, lambda m: _collect(sent, m))

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR

    async def test_passes_through_non_http(self, setup_tracer) -> None:
        exporter = setup_tracer
        called = False

        async def ws_app(scope, receive, send):
            nonlocal called
            called = True

        app = TracingMiddleware(ws_app)
        await app({"type": "websocket"}, _receive, lambda m: _noop())

        assert called
        assert len(exporter.get_finished_spans()) == 0

    async def test_records_exception(self, setup_tracer) -> None:
        exporter = setup_tracer

        async def failing_app(scope, receive, send):
            raise RuntimeError("crash")

        app = TracingMiddleware(failing_app)

        with pytest.raises(RuntimeError, match="crash"):
            await app(_make_scope(), _receive, lambda m: _noop())

        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR


async def _collect(lst, msg):
    lst.append(msg)


async def _noop():
    pass

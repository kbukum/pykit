"""Extended tests for server middleware: Prometheus + tracing edge cases."""

from __future__ import annotations

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import REGISTRY

from pykit_server_middleware.prometheus import PrometheusMiddleware
from pykit_server_middleware.tracing import TracingMiddleware

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_sample_value(name: str, labels: dict[str, str]) -> float | None:
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name == name and all(sample.labels.get(k) == v for k, v in labels.items()):
                return sample.value
    return None


def _make_scope(
    method: str = "GET",
    path: str = "/test",
    scheme: str = "http",
    headers: list[tuple[bytes, bytes]] | None = None,
) -> dict:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "scheme": scheme,
        "headers": headers or [],
    }


async def _simple_app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"hello"})


async def _app_status(status: int):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    return app


async def _receive():
    return {"type": "http.request", "body": b""}


async def _noop():
    pass


# ---------------------------------------------------------------------------
# Prometheus middleware — extended
# ---------------------------------------------------------------------------


class TestPrometheusExtended:
    async def test_custom_metrics_path(self) -> None:
        app = PrometheusMiddleware(_simple_app, metrics_path="/healthz/metrics")
        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        scope = _make_scope(path="/healthz/metrics")
        await app(scope, _receive, send)
        assert sent[0]["status"] == 200
        body = sent[1].get("body", b"")
        assert len(body) > 0

    async def test_normal_path_not_intercepted(self) -> None:
        """Normal paths should pass through to the inner app, not serve metrics."""
        inner_called = False

        async def inner_app(scope, receive, send):
            nonlocal inner_called
            inner_called = True
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"ok"})

        app = PrometheusMiddleware(inner_app, metrics_path="/metrics")
        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        await app(_make_scope(path="/api/data"), _receive, send)
        assert inner_called
        assert sent[0]["status"] == 200

    async def test_records_request_size_from_content_length(self) -> None:
        app = PrometheusMiddleware(_simple_app)
        sent: list[dict] = []

        scope = _make_scope(
            method="POST",
            path="/req-size-test",
            headers=[(b"content-length", b"1024")],
        )
        await app(scope, _receive, lambda m: _collect(sent, m))

        val = _get_sample_value(
            "http_request_size_bytes_count",
            {"method": "POST", "path": "/req-size-test"},
        )
        assert val is not None and val >= 1.0

    async def test_no_request_size_when_missing_content_length(self) -> None:
        """When content-length is absent, request_size should not be observed."""
        app = PrometheusMiddleware(_simple_app)
        # Using a unique path to isolate the metric
        scope = _make_scope(method="GET", path="/no-cl-unique-test")
        await app(scope, _receive, lambda m: _noop())

        val = _get_sample_value(
            "http_request_size_bytes_count",
            {"method": "GET", "path": "/no-cl-unique-test"},
        )
        # Should be None or 0 — no observation when content-length absent
        assert val is None or val == 0.0

    @pytest.mark.parametrize("status", [200, 201, 301, 400, 404, 500, 503])
    async def test_records_various_status_codes(self, status: int) -> None:
        async def app_with_status(scope, receive, send):
            await send({"type": "http.response.start", "status": status, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        path = f"/status-{status}-test"
        app = PrometheusMiddleware(app_with_status)
        await app(_make_scope(path=path), _receive, lambda m: _noop())

        val = _get_sample_value(
            "http_requests_total",
            {"method": "GET", "path": path, "status_code": str(status)},
        )
        assert val is not None and val >= 1.0

    async def test_records_response_size_large_body(self) -> None:
        body_data = b"x" * 10000

        async def big_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": body_data})

        app = PrometheusMiddleware(big_app)
        path = "/big-response-test"
        await app(_make_scope(path=path), _receive, lambda m: _noop())

        val = _get_sample_value(
            "http_response_size_bytes_sum",
            {"method": "GET", "path": path},
        )
        assert val is not None and val >= 10000.0

    async def test_records_response_size_multiple_chunks(self) -> None:
        async def chunked_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"abc"})
            await send({"type": "http.response.body", "body": b"def"})

        app = PrometheusMiddleware(chunked_app)
        path = "/chunked-test"
        sent: list[dict] = []
        await app(_make_scope(path=path), _receive, lambda m: _collect(sent, m))

        val = _get_sample_value(
            "http_response_size_bytes_sum",
            {"method": "GET", "path": path},
        )
        assert val is not None and val >= 6.0

    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def test_records_various_methods(self, method: str) -> None:
        path = f"/method-{method.lower()}-test"
        app = PrometheusMiddleware(_simple_app)
        await app(_make_scope(method=method, path=path), _receive, lambda m: _noop())

        val = _get_sample_value(
            "http_requests_total",
            {"method": method, "path": path, "status_code": "200"},
        )
        assert val is not None and val >= 1.0

    async def test_records_metrics_even_on_app_exception(self) -> None:
        async def failing_app(scope, receive, send):
            raise RuntimeError("boom")

        app = PrometheusMiddleware(failing_app)
        path = "/fail-metrics-test"

        with pytest.raises(RuntimeError, match="boom"):
            await app(_make_scope(path=path), _receive, lambda m: _noop())

        val = _get_sample_value(
            "http_requests_total",
            {"method": "GET", "path": path, "status_code": "200"},
        )
        # Even on exception, the finally block should record metrics
        assert val is not None and val >= 1.0

    async def test_metrics_endpoint_content_type(self) -> None:
        app = PrometheusMiddleware(_simple_app)
        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        await app(_make_scope(path="/metrics"), _receive, send)
        headers = dict(sent[0].get("headers", []))
        assert headers[b"content-type"] == b"text/plain; charset=utf-8"


# ---------------------------------------------------------------------------
# Tracing middleware — extended
# ---------------------------------------------------------------------------


@pytest.fixture()
def tracer_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(provider)
    yield exporter
    provider.shutdown()


class TestTracingExtended:
    async def test_custom_service_name(self, tracer_exporter) -> None:
        app = TracingMiddleware(_simple_app, service_name="my.api")
        sent: list[dict] = []
        await app(_make_scope(), _receive, lambda m: _collect(sent, m))

        spans = tracer_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].instrumentation_info.name == "my.api"

    async def test_4xx_not_marked_as_error(self, tracer_exporter) -> None:
        async def not_found_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 404, "headers": []})
            await send({"type": "http.response.body", "body": b"not found"})

        app = TracingMiddleware(not_found_app)
        await app(_make_scope(), _receive, lambda m: _noop())

        spans = tracer_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code != trace.StatusCode.ERROR

    async def test_span_name_format(self, tracer_exporter) -> None:
        app = TracingMiddleware(_simple_app)
        await app(
            _make_scope(method="DELETE", path="/items/42"),
            _receive,
            lambda m: _noop(),
        )
        spans = tracer_exporter.get_finished_spans()
        assert spans[0].name == "DELETE /items/42"

    async def test_scheme_attribute(self, tracer_exporter) -> None:
        app = TracingMiddleware(_simple_app)
        await app(
            _make_scope(scheme="https"),
            _receive,
            lambda m: _noop(),
        )
        spans = tracer_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes or {})
        assert attrs["http.scheme"] == "https"

    async def test_status_code_attribute_set(self, tracer_exporter) -> None:
        async def created_app(scope, receive, send):
            await send({"type": "http.response.start", "status": 201, "headers": []})
            await send({"type": "http.response.body", "body": b""})

        app = TracingMiddleware(created_app)
        await app(_make_scope(), _receive, lambda m: _noop())

        spans = tracer_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes or {})
        assert attrs["http.status_code"] == 201

    async def test_response_headers_contain_trace_context(self, tracer_exporter) -> None:
        app = TracingMiddleware(_simple_app)
        sent: list[dict] = []
        await app(_make_scope(), _receive, lambda m: _collect(sent, m))

        # The first message is http.response.start and should have tracing headers
        start_msg = sent[0]
        header_names = [k.decode("latin-1") for k, v in start_msg.get("headers", [])]
        assert "traceparent" in header_names

    async def test_exception_propagates(self, tracer_exporter) -> None:
        async def boom(scope, receive, send):
            raise ValueError("test error")

        app = TracingMiddleware(boom)
        with pytest.raises(ValueError, match="test error"):
            await app(_make_scope(), _receive, lambda m: _noop())

        spans = tracer_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].status.status_code == trace.StatusCode.ERROR
        events = spans[0].events
        assert any(e.name == "exception" for e in events)

    @pytest.mark.parametrize(
        "method, path",
        [
            ("GET", "/"),
            ("POST", "/api/users"),
            ("PUT", "/api/users/1"),
            ("PATCH", "/settings"),
        ],
    )
    async def test_multiple_methods_and_paths(self, tracer_exporter, method: str, path: str) -> None:
        app = TracingMiddleware(_simple_app)
        await app(_make_scope(method=method, path=path), _receive, lambda m: _noop())

        spans = tracer_exporter.get_finished_spans()
        assert len(spans) == 1
        assert spans[0].name == f"{method} {path}"
        attrs = dict(spans[0].attributes or {})
        assert attrs["http.method"] == method
        assert attrs["http.target"] == path


# ---------------------------------------------------------------------------
# Middleware chaining
# ---------------------------------------------------------------------------


class TestMiddlewareChaining:
    async def test_tracing_and_prometheus_together(self, tracer_exporter) -> None:
        """Both middlewares applied should work without interference."""
        inner = _simple_app
        traced = TracingMiddleware(inner)
        measured = PrometheusMiddleware(traced)

        path = "/chained-test"
        sent: list[dict] = []
        await measured(_make_scope(path=path), _receive, lambda m: _collect(sent, m))

        # Tracing should have created a span
        spans = tracer_exporter.get_finished_spans()
        assert len(spans) == 1

        # Prometheus should have recorded the request
        val = _get_sample_value(
            "http_requests_total",
            {"method": "GET", "path": path, "status_code": "200"},
        )
        assert val is not None and val >= 1.0


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------


async def _collect(lst: list, msg):
    lst.append(msg)

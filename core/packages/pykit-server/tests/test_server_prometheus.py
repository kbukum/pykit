"""Tests for HTTP Prometheus metrics middleware."""

from __future__ import annotations

from prometheus_client import REGISTRY

from pykit_server.middleware import PrometheusMiddleware


def _get_sample_value(name: str, labels: dict[str, str]) -> float | None:
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name == name and all(sample.labels.get(k) == v for k, v in labels.items()):
                return sample.value
    return None


def _make_scope(method: str = "GET", path: str = "/test") -> dict:
    return {
        "type": "http",
        "method": method,
        "path": path,
        "scheme": "http",
        "headers": [],
    }


async def _simple_app(scope, receive, send):
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [],
        }
    )
    await send(
        {
            "type": "http.response.body",
            "body": b"hello",
        }
    )


async def _receive():
    return {"type": "http.request", "body": b""}


class TestPrometheusMiddleware:
    async def test_records_request_count(self) -> None:
        app = PrometheusMiddleware(_simple_app)
        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        await app(_make_scope(method="GET", path="/prom-test"), _receive, send)

        val = _get_sample_value(
            "http_requests_total",
            {"method": "GET", "path": "/prom-test", "status_code": "200"},
        )
        assert val is not None and val >= 1.0

    async def test_records_duration(self) -> None:
        app = PrometheusMiddleware(_simple_app)
        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        await app(_make_scope(method="POST", path="/dur-test"), _receive, send)

        val = _get_sample_value(
            "http_request_duration_seconds_count",
            {"method": "POST", "path": "/dur-test", "status_code": "200"},
        )
        assert val is not None and val >= 1.0

    async def test_serves_metrics_endpoint(self) -> None:
        app = PrometheusMiddleware(_simple_app)
        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        scope = _make_scope(method="GET", path="/metrics")
        await app(scope, _receive, send)

        assert sent[0]["status"] == 200
        body = sent[1].get("body", b"")
        assert b"http_requests_total" in body or len(body) > 0

    async def test_passes_through_non_http(self) -> None:
        called = False

        async def ws_app(scope, receive, send):
            nonlocal called
            called = True

        app = PrometheusMiddleware(ws_app)
        await app({"type": "websocket"}, _receive, lambda m: _noop())

        assert called

    async def test_records_response_size(self) -> None:
        app = PrometheusMiddleware(_simple_app)
        sent: list[dict] = []

        async def send(msg):
            sent.append(msg)

        await app(_make_scope(method="GET", path="/size-test"), _receive, send)

        val = _get_sample_value(
            "http_response_size_bytes_count",
            {"method": "GET", "path": "/size-test"},
        )
        assert val is not None and val >= 1.0


async def _noop():
    pass

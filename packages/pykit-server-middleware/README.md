# pykit-server-middleware

ASGI middleware for HTTP server observability: Prometheus metrics collection and OpenTelemetry distributed tracing.

## Installation

```bash
pip install pykit-server-middleware
# or
uv add pykit-server-middleware
```

## Quick Start

```python
from pykit_server_middleware import PrometheusMiddleware, TracingMiddleware

# Wrap any ASGI application (Starlette, FastAPI, etc.)
app = PrometheusMiddleware(
    TracingMiddleware(app, service_name="orders"),
    service_name="orders",
    metrics_path="/metrics",
)

# PrometheusMiddleware exposes /metrics endpoint automatically
# TracingMiddleware creates spans per request with W3C trace context propagation
```

### Prometheus Metrics Collected

```
http_requests_total{method, path, status_code}          — Counter
http_request_duration_seconds{method, path, status_code} — Histogram
http_request_size_bytes{method, path}                    — Histogram
http_response_size_bytes{method, path}                   — Histogram
```

## Key Components

- **PrometheusMiddleware** — ASGI middleware that records HTTP request/response metrics and serves a `/metrics` endpoint in Prometheus text format
- **TracingMiddleware** — ASGI middleware that creates OpenTelemetry spans per HTTP request, extracts/injects W3C TraceContext headers, and records errors on 5xx responses

## Dependencies

- `opentelemetry-api`
- `prometheus-client`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

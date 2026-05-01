# pykit-server

gRPC server bootstrap with health checking, graceful shutdown, secure-by-default reflection, request interceptors, and folded HTTP/ASGI middleware.

## Installation

```bash
pip install pykit-server
# or
uv add pykit-server
```

## Quick Start

```python
import grpc
from pykit_server import BaseServer, LoggingInterceptor, MetricsInterceptor, TenantInterceptor

class OrderServer(BaseServer):
    async def register_services(self, server: grpc.aio.Server) -> None:
        orders_pb2_grpc.add_OrderServiceServicer_to_server(OrderServiceImpl(), server)

server = OrderServer(
    port=50051,
    reflection_enabled=True,  # enable only in development
    interceptors=[
        LoggingInterceptor(),
        TenantInterceptor(),
        MetricsInterceptor(collector=my_metrics_collector),
    ],
)

await server.start()
await server.run()
```

## HTTP Middleware

```python
from pykit_server import (
    HttpTenantConfig,
    PrometheusMiddleware,
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimiter,
    TenantMiddleware,
    TracingMiddleware,
)

app = TracingMiddleware(app, service_name="orders")
app = TenantMiddleware(app, HttpTenantConfig(skip_paths=frozenset({"/healthz"})))
app = RateLimitMiddleware(app, RateLimiter(RateLimitConfig(requests_per_minute=120)))
app = PrometheusMiddleware(app)
```

Ordering target: tracing -> logging -> auth -> validation -> handler -> metrics. When HTTP rate limiting is enabled, place it after identity extraction/validation so per-user or per-tenant keys are stable, then terminate with metrics outermost. `pykit-server` supplies tracing, tenant/auth-adjacent extraction, rate limiting through `pykit-resilience`, and metrics; compose custom logging/auth/validation middleware in the documented order.

## Key Components

- **BaseServer** — async gRPC server with health checking, optional reflection, TLS port binding, and graceful shutdown
- **LoggingInterceptor / ErrorHandlingInterceptor / MetricsInterceptor** — gRPC transport interceptors
- **TenantInterceptor** — gRPC tenant extraction shared with HTTP tenant context
- **TracingMiddleware / PrometheusMiddleware / TenantMiddleware / RateLimitMiddleware** — folded HTTP middleware for ASGI apps
- **RateLimiter** — per-key rate limit registry backed by `pykit-resilience`

## Security Notes

- gRPC reflection is **disabled by default**; enable it explicitly for development only.
- Use `pykit-security` TLS contexts to keep the workspace default at TLS 1.3 with a TLS 1.2 floor where the transport exposes version controls; Python gRPC secure credentials do not currently expose the full floor/cipher surface, so parity-sensitive enforcement remains bounded by the upstream runtime.
- HTTP middleware uses bounded per-client queues/rate limiting and never forwards tenant identity via query string.

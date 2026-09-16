# pykit-server

Bootstrap gRPC servers and compose HTTP middleware with health, tracing, metrics, tenant handling, and graceful shutdown.

## Installation

```bash
pip install pykit-server
# or
uv add pykit-server
```

## Quick start

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

## HTTP middleware

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
app = PrometheusMiddleware(app, service_name="orders")
```

Recommended order is tracing -> logging -> auth -> validation -> handler -> metrics. When rate limiting is enabled, place it after identity extraction and validation so per-user or per-tenant keys stay stable, then keep metrics outermost.

## What it includes

- **`BaseServer`** for async gRPC startup, shutdown, TLS port binding, health checks, and optional reflection.
- **`HealthRegistry`** for registering liveness and readiness checks.
- **`LoggingInterceptor`**, **`ErrorHandlingInterceptor`**, and **`MetricsInterceptor`** for gRPC transport concerns.
- **`TenantInterceptor`**, **`TenantMiddleware`**, and tenant helpers such as `get_tenant()` and `require_tenant()`.
- **`TracingMiddleware`**, **`PrometheusMiddleware`**, **`RateLimiter`**, and **`RateLimitMiddleware`** for ASGI applications.
- **`ip_based_key()`** and **`user_based_key()`** helpers for rate-limit key selection.

## Security notes

- gRPC reflection is **disabled by default**. Turn it on explicitly for development only.
- Use `pykit-security` TLS contexts to keep the workspace default at TLS 1.3 with a TLS 1.2 floor where the transport exposes version controls. Python gRPC secure credentials do not currently expose the full floor and cipher surface, so parity-sensitive enforcement remains bounded by the upstream runtime.
- HTTP middleware never forwards tenant identity through query strings and uses bounded rate-limiting state.

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)

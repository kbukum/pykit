# pykit-server

gRPC server bootstrap with health checking, reflection, graceful shutdown, and request interceptors. Implements the Component protocol.

## Installation

```bash
pip install pykit-server
# or
uv add pykit-server
```

## Quick Start

```python
import grpc
from pykit_server import BaseServer
from pykit_server.interceptors import (
    LoggingInterceptor, ErrorHandlingInterceptor, MetricsInterceptor,
)

class OrderServer(BaseServer):
    async def register_services(self, server: grpc.aio.Server) -> None:
        orders_pb2_grpc.add_OrderServiceServicer_to_server(OrderServiceImpl(), server)

server = OrderServer(
    port=50051,
    interceptors=[
        LoggingInterceptor(),
        ErrorHandlingInterceptor(),
        MetricsInterceptor(collector=my_metrics_collector),
    ],
)

# Component protocol: name and health
print(server.name)  # "grpc-server"
health = await server.health()  # Health(status=UNHEALTHY, message="not running")

await server.start()  # Starts gRPC server with health + reflection
health = await server.health()  # Health(status=HEALTHY, message="serving")

# Fine-grained service health
server.set_service_status("orders.v1.OrderService", serving=True)

await server.run()  # start + signal handlers + wait for shutdown
```

## Key Components

- **BaseServer** — Async gRPC server with health checking, reflection, and graceful shutdown. Implements Component protocol (`name` property, `health()` method)
- **HealthServicer** — Re-exported `grpc_health.v1.health.HealthServicer` for convenience
- **LoggingInterceptor** — Logs every gRPC request with method name, duration, and status
- **ErrorHandlingInterceptor** — Catches `AppError` and translates to proper gRPC status codes
- **MetricsInterceptor** — Records request metrics via a pluggable collector with `observe_request()`

## Dependencies

- `pykit-component`, `pykit-errors`, `pykit-logging`
- `grpcio`, `grpcio-health-checking`, `grpcio-reflection`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

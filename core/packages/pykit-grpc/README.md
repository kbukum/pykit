# pykit-grpc

Client-side gRPC utilities: async channel management, lifecycle component, and bidirectional error mapping.

## Installation

```bash
pip install pykit-grpc
# or
uv add pykit-grpc
```

## Quick Start

```python
import asyncio
from pykit_grpc import GrpcConfig, GrpcChannel, GrpcComponent, grpc_error_to_app_error

# Direct channel usage
config = GrpcConfig(target="localhost:50051", timeout=30.0)
channel = GrpcChannel(config)

stub = MyServiceStub(channel.channel)  # use underlying grpc.aio.Channel
try:
    response = await stub.GetItem(request)
except grpc.RpcError as e:
    app_err = grpc_error_to_app_error(e)  # → NotFoundError, etc.
    raise app_err

connected = await channel.ping()  # True if READY
await channel.close()

# Component lifecycle (integrates with pykit-bootstrap)
component = GrpcComponent(config, component_name="user-service")
await component.start()
health = await component.health()  # HEALTHY / DEGRADED / UNHEALTHY
await component.stop()
```

## Key Components

- **GrpcConfig** — Configuration dataclass: `target`, `insecure`, `timeout`, `max_message_size` (4MB default), `keepalive_time`, `keepalive_timeout`
- **GrpcChannel** — Async gRPC channel wrapper with `channel` property, `ping()` connectivity check, and `close()` shutdown; creates insecure or TLS channels based on config
- **GrpcComponent** — Component protocol implementation wrapping `GrpcChannel` with `start()`, `stop()`, and `health()` (HEALTHY/DEGRADED/UNHEALTHY based on connectivity)
- **grpc_error_to_app_error(err)** — Converts `grpc.RpcError` to typed `AppError` subtypes (NotFoundError, InvalidInputError, ServiceUnavailableError, TimeoutError, or generic AppError)
- **app_error_to_grpc_status(err)** — Converts `AppError` to `(grpc.StatusCode, str)` tuple for server-side error responses

## Dependencies

- `grpcio` — gRPC Python library
- `pykit-errors` — Error types and mapping
- `pykit-component` — Component lifecycle protocol

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

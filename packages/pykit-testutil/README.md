# pykit-testutil

Test utilities for gRPC services: mock server, pytest fixtures, and channel helpers.

## Installation

```bash
pip install pykit-testutil
# or
uv add pykit-testutil
```

## Quick Start

```python
from pykit_testutil import MockGrpcServer, grpc_server_fixture, grpc_channel_fixture

# Using MockGrpcServer as an async context manager
async with MockGrpcServer() as server:
    await server.start(add_MyServiceServicer_to_server, MyServiceImpl())
    print(server.address)  # "localhost:50123"
    print(server.port)     # 50123

    # Create a channel to the mock server
    async for channel in grpc_channel_fixture(server.port):
        stub = MyServiceStub(channel)
        response = await stub.GetItem(GetItemRequest(id="abc"))

# Using fixtures in pytest
async def test_my_service():
    async for server, port in grpc_server_fixture(
        add_MyServiceServicer_to_server, MyServiceImpl()
    ):
        async for channel in grpc_channel_fixture(port):
            stub = MyServiceStub(channel)
            resp = await stub.GetItem(GetItemRequest(id="1"))
            assert resp.name == "expected"
```

## Key Components

- **MockGrpcServer** — Lightweight mock gRPC server with async context manager support, auto port selection, and `start()`/`stop()` lifecycle
- **grpc_server_fixture()** — Async generator that starts a gRPC server with a given servicer and yields `(server, port)`
- **grpc_channel_fixture()** — Async generator that provides an insecure gRPC channel to a given port

## Dependencies

- `grpcio`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

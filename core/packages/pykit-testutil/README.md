# pykit-testutil

Test gRPC services with reusable mock servers, fixtures, assertions, fakes, and strategies.

## Installation

```bash
pip install pykit-testutil
# or
uv add pykit-testutil
```

## Quick start

```python
from pykit_testutil import MockGrpcServer, grpc_channel_fixture, grpc_server_fixture

async with MockGrpcServer() as server:
    await server.start(add_MyServiceServicer_to_server, MyServiceImpl())

    async for channel in grpc_channel_fixture(server.port):
        stub = MyServiceStub(channel)
        response = await stub.GetItem(GetItemRequest(id="abc"))

async def test_my_service() -> None:
    async for server, port in grpc_server_fixture(add_MyServiceServicer_to_server, MyServiceImpl()):
        async for channel in grpc_channel_fixture(port):
            stub = MyServiceStub(channel)
            response = await stub.GetItem(GetItemRequest(id="1"))
            assert response.name == "expected"
```

## What it includes

- **`MockGrpcServer`** starts a lightweight async gRPC server with automatic port selection.
- **`grpc_server_fixture()`** and **`grpc_channel_fixture()`** provide async pytest-friendly setup helpers.
- **`assert_ok()`** and **`assert_err()`** make result and error assertions shorter.
- **`FakeAsyncKeyValue`** is a small async fake for cache or key-value style tests.
- **`error_codes()`**, **`non_empty_text()`**, and **`url_safe_text()`** provide Hypothesis strategies.
- **`integration`**, **`requires_network`**, and **`slow`** expose reusable pytest markers.

## Dependencies

- `grpcio`
- `pytest>=8`

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)

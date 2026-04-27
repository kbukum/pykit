"""Pytest fixtures for gRPC service testing and common async test utilities."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any

import pytest
from grpc import aio


async def grpc_server_fixture(
    servicer_adder: Any,
    servicer: Any,
    *,
    port: int = 0,
) -> AsyncGenerator[tuple[aio.Server, int]]:
    """Pytest fixture that starts a gRPC server with the given servicer.

    Usage:
        async def test_my_service():
            async for server, port in grpc_server_fixture(
                add_MyServiceServicer_to_server, MyServicer()
            ):
                async with aio.insecure_channel(f"localhost:{port}") as channel:
                    stub = MyServiceStub(channel)
                    response = await stub.MyMethod(request)
    """
    server = aio.server()
    servicer_adder(servicer, server)
    actual_port = server.add_insecure_port(f"localhost:{port}")
    await server.start()
    try:
        yield server, actual_port
    finally:
        await server.stop(0)


async def grpc_channel_fixture(
    port: int,
) -> AsyncGenerator[aio.Channel]:
    """Pytest fixture that provides an insecure gRPC channel."""
    async with aio.insecure_channel(f"localhost:{port}") as channel:
        yield channel


@pytest.fixture
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Create a new event loop for each test (avoids cross-test contamination)."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def anyio_backend() -> str:
    """Use asyncio backend for anyio tests."""
    return "asyncio"

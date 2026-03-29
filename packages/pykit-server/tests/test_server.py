"""Tests for pykit.server.BaseServer."""

from __future__ import annotations

import grpc
import pytest
from grpc_health.v1 import health_pb2, health_pb2_grpc

from pykit_server import BaseServer


@pytest.mark.asyncio
async def test_server_start_stop() -> None:
    """Server should start, respond to health checks, and stop gracefully."""
    server = BaseServer(port=0)
    # Use port 0 to let OS assign a free port
    # BaseServer binds to host:port, so we need a known port for testing
    server.port = 50199  # Use a high port unlikely to conflict
    await server.start()
    assert server.health_servicer is not None
    await server.stop()


@pytest.mark.asyncio
async def test_server_health_check() -> None:
    """Health check should return SERVING after start."""
    server = BaseServer(port=50198)
    await server.start()
    try:
        async with grpc.aio.insecure_channel("localhost:50198") as channel:
            stub = health_pb2_grpc.HealthStub(channel)
            response = await stub.Check(health_pb2.HealthCheckRequest(service=""))
            assert response.status == health_pb2.HealthCheckResponse.SERVING
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_set_service_status() -> None:
    """set_service_status should update health for named services."""
    server = BaseServer(port=50197)
    await server.start()
    try:
        async with grpc.aio.insecure_channel("localhost:50197") as channel:
            stub = health_pb2_grpc.HealthStub(channel)

            server.set_service_status("my-service", serving=True)
            response = await stub.Check(health_pb2.HealthCheckRequest(service="my-service"))
            assert response.status == health_pb2.HealthCheckResponse.SERVING

            server.set_service_status("my-service", serving=False)
            response = await stub.Check(health_pb2.HealthCheckRequest(service="my-service"))
            assert response.status == health_pb2.HealthCheckResponse.NOT_SERVING
    finally:
        await server.stop()

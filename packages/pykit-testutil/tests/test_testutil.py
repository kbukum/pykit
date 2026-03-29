"""Tests for pykit_testutil package."""

from __future__ import annotations

import pytest

from pykit_testutil import MockGrpcServer, grpc_channel_fixture, grpc_server_fixture

# ---------------------------------------------------------------------------
# MockGrpcServer — init and properties
# ---------------------------------------------------------------------------


class TestMockGrpcServerInit:
    def test_initial_port_is_zero(self) -> None:
        server = MockGrpcServer()
        assert server.port == 0

    def test_address_property(self) -> None:
        server = MockGrpcServer()
        assert server.address == "localhost:0"

    def test_internal_server_is_none(self) -> None:
        server = MockGrpcServer()
        assert server._server is None


# ---------------------------------------------------------------------------
# MockGrpcServer — async context manager
# ---------------------------------------------------------------------------


class TestMockGrpcServerContextManager:
    @pytest.mark.asyncio
    async def test_aenter_returns_self(self) -> None:
        server = MockGrpcServer()
        result = await server.__aenter__()
        assert result is server

    @pytest.mark.asyncio
    async def test_aexit_without_start_does_not_raise(self) -> None:
        server = MockGrpcServer()
        async with server as s:
            assert s is server
        # Exiting the context manager when no server started should be safe
        assert server._server is None


# ---------------------------------------------------------------------------
# Public API — import check
# ---------------------------------------------------------------------------


class TestPublicAPI:
    def test_all_public_symbols_accessible(self) -> None:
        import pykit_testutil

        for name in pykit_testutil.__all__:
            assert hasattr(pykit_testutil, name), f"{name} not accessible on pykit_testutil"

    def test_mock_grpc_server_is_exported(self) -> None:
        assert MockGrpcServer is not None

    def test_grpc_server_fixture_is_exported(self) -> None:
        assert callable(grpc_server_fixture)

    def test_grpc_channel_fixture_is_exported(self) -> None:
        assert callable(grpc_channel_fixture)

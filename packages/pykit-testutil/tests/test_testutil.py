"""Tests for pykit_testutil package."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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
# MockGrpcServer — start / stop with mock servicer
# ---------------------------------------------------------------------------


class TestMockGrpcServerStartStop:
    @pytest.mark.asyncio
    async def test_start_and_stop(self) -> None:
        """Cover mock_server.py lines 37-47: full start/stop cycle."""
        mock_aio_server = MagicMock()
        mock_aio_server.add_insecure_port.return_value = 50051
        mock_aio_server.start = AsyncMock()
        mock_aio_server.stop = AsyncMock()

        with patch("pykit_testutil.mock_server.aio.server", return_value=mock_aio_server):
            server = MockGrpcServer()
            servicer_adder = MagicMock()
            servicer = MagicMock()

            port = await server.start(servicer_adder, servicer)
            assert port == 50051
            assert server.port == 50051
            assert server.address == "localhost:50051"
            servicer_adder.assert_called_once_with(servicer, mock_aio_server)
            mock_aio_server.start.assert_awaited_once()

            await server.stop()
            mock_aio_server.stop.assert_awaited_once_with(0)
            assert server._server is None

    @pytest.mark.asyncio
    async def test_stop_when_not_started(self) -> None:
        """Cover mock_server.py lines 45-46: stop is no-op when _server is None."""
        server = MockGrpcServer()
        await server.stop()  # should not raise

    @pytest.mark.asyncio
    async def test_context_manager_with_start(self) -> None:
        """Cover mock_server.py lines 49-53: __aenter__/__aexit__ with a started server."""
        mock_aio_server = MagicMock()
        mock_aio_server.add_insecure_port.return_value = 50052
        mock_aio_server.start = AsyncMock()
        mock_aio_server.stop = AsyncMock()

        with patch("pykit_testutil.mock_server.aio.server", return_value=mock_aio_server):
            async with MockGrpcServer() as server:
                await server.start(MagicMock(), MagicMock())
                assert server.port == 50052
            # __aexit__ calls stop
            mock_aio_server.stop.assert_awaited_once_with(0)


# ---------------------------------------------------------------------------
# grpc_server_fixture
# ---------------------------------------------------------------------------


class TestGrpcServerFixture:
    @pytest.mark.asyncio
    async def test_grpc_server_fixture(self) -> None:
        """Cover fixtures.py lines 30-37: server fixture starts and stops."""
        mock_aio_server = MagicMock()
        mock_aio_server.add_insecure_port.return_value = 50053
        mock_aio_server.start = AsyncMock()
        mock_aio_server.stop = AsyncMock()

        servicer_adder = MagicMock()
        servicer = MagicMock()

        with patch("pykit_testutil.fixtures.aio.server", return_value=mock_aio_server):
            async for _server, port in grpc_server_fixture(servicer_adder, servicer):
                assert port == 50053
                servicer_adder.assert_called_once_with(servicer, mock_aio_server)
                mock_aio_server.start.assert_awaited_once()
            mock_aio_server.stop.assert_awaited_once_with(0)


# ---------------------------------------------------------------------------
# grpc_channel_fixture
# ---------------------------------------------------------------------------


class TestGrpcChannelFixture:
    @pytest.mark.asyncio
    async def test_grpc_channel_fixture(self) -> None:
        """Cover fixtures.py lines 40-45: channel fixture yields a channel."""
        mock_channel = AsyncMock()

        with patch("pykit_testutil.fixtures.aio.insecure_channel") as mock_insecure_channel:
            mock_ctx = AsyncMock()
            mock_ctx.__aenter__.return_value = mock_channel
            mock_ctx.__aexit__.return_value = False
            mock_insecure_channel.return_value = mock_ctx

            async for channel in grpc_channel_fixture(50053):
                assert channel is mock_channel


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

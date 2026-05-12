"""Mock gRPC server for testing."""

from __future__ import annotations

from typing import Any

from grpc import aio


class MockGrpcServer:
    """A lightweight mock gRPC server for unit testing.

    Provides a simple way to set up a test gRPC server with custom servicers.
    """

    def __init__(self) -> None:
        self._server: aio.Server | None = None
        self._port: int = 0

    @property
    def port(self) -> int:
        return self._port

    @property
    def address(self) -> str:
        return f"localhost:{self._port}"

    async def start(
        self,
        servicer_adder: Any,
        servicer: Any,
    ) -> int:
        """Start the mock server with the given servicer.

        Returns the port the server is listening on.
        """
        self._server = aio.server()
        servicer_adder(servicer, self._server)
        self._port = self._server.add_insecure_port("localhost:0")
        await self._server.start()
        return self._port

    async def stop(self) -> None:
        """Stop the mock server."""
        if self._server is not None:
            await self._server.stop(0)
            self._server = None

    async def __aenter__(self) -> MockGrpcServer:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.stop()

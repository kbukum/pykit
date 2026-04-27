"""pykit_testutil — Test utilities for gRPC services."""

from __future__ import annotations

from pykit_testutil.assertions import assert_err, assert_ok
from pykit_testutil.fixtures import anyio_backend, event_loop, grpc_channel_fixture, grpc_server_fixture
from pykit_testutil.hypothesis_strategies import error_codes, non_empty_text, url_safe_text
from pykit_testutil.markers import integration, requires_network, slow
from pykit_testutil.mock_server import MockGrpcServer

__all__ = [
    "MockGrpcServer",
    "anyio_backend",
    "assert_err",
    "assert_ok",
    "error_codes",
    "event_loop",
    "grpc_channel_fixture",
    "grpc_server_fixture",
    "integration",
    "non_empty_text",
    "requires_network",
    "slow",
    "url_safe_text",
]

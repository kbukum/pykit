"""pykit-grpc — Client-side gRPC utilities: channel management, lifecycle, and error mapping."""

from __future__ import annotations

from pykit_grpc.channel import GrpcChannel
from pykit_grpc.component import GrpcComponent
from pykit_grpc.config import GrpcConfig
from pykit_grpc.discovery_channel import DiscoveryChannel
from pykit_grpc.errors import (
    app_error_to_grpc_status,
    app_error_to_grpc_trailing_metadata,
    grpc_error_to_app_error,
)

__all__ = [
    "DiscoveryChannel",
    "GrpcChannel",
    "GrpcComponent",
    "GrpcConfig",
    "app_error_to_grpc_status",
    "app_error_to_grpc_trailing_metadata",
    "grpc_error_to_app_error",
]

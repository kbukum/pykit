"""gRPC client connection configuration."""

from __future__ import annotations

from dataclasses import dataclass

_4MB = 4 * 1024 * 1024


@dataclass
class GrpcConfig:
    """Configuration for a gRPC client channel.

    Mirrors gokit ``grpc.Config`` with Python-appropriate defaults.
    """

    target: str = "localhost:50051"
    insecure: bool = True
    timeout: float = 30.0
    max_message_size: int = _4MB
    keepalive_time: float = 30.0
    keepalive_timeout: float = 10.0

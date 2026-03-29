"""Redis configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RedisConfig:
    """Connection and pool configuration for Redis."""

    name: str = "redis"
    url: str = "redis://localhost:6379/0"
    password: str = ""
    db: int = 0
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    retry_on_timeout: bool = True
    decode_responses: bool = True
    enabled: bool = True

"""Cache configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CacheConfig:
    """Configuration for selecting and constructing a cache backend."""

    name: str = "cache"
    backend: str = "memory"
    enabled: bool = True
    default_ttl_seconds: int | None = None
    max_entries: int = 10_000

    # Redis adapter settings. Used only by pykit_cache.redis after explicit registration.
    url: str = "redis://localhost:6379/0"
    password: str = ""
    db: int = 0
    max_connections: int = 10
    socket_timeout: float = 5.0
    socket_connect_timeout: float = 5.0
    retry_on_timeout: bool = True
    decode_responses: bool = True

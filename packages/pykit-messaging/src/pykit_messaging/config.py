"""Broker-agnostic configuration base."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class BrokerConfig:
    """Base configuration shared by all broker backends."""

    name: str = ""
    enabled: bool = True
    brokers: list[str] = field(default_factory=list)
    retries: int = 3
    request_timeout_ms: int = 30000

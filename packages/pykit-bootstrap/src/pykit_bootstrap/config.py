"""Application configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AppConfig:
    """Base application configuration.

    Provides common settings every service needs. Extend via
    composition or subclassing for service-specific fields.
    """

    name: str
    version: str = "dev"
    env: str = "development"
    debug: bool = False
    graceful_timeout: float = 30.0
    extra: dict[str, str] = field(default_factory=dict)

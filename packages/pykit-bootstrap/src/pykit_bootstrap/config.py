"""Application configuration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable


class Environment(StrEnum):
    """Application environment."""

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass(frozen=True)
class LoggingConfig:
    """Logging configuration."""

    level: str = "INFO"
    format: str = "console"  # "json" or "console"


@dataclass(frozen=True)
class ServiceConfig:
    """Base service configuration shared across all services."""

    name: str = ""
    environment: Environment = Environment.DEVELOPMENT
    version: str = "0.0.0"
    debug: bool = False
    logging: LoggingConfig = field(default_factory=LoggingConfig)


@runtime_checkable
class AppConfig(Protocol):
    """Protocol that all service configurations must implement."""

    def apply_defaults(self) -> None:
        """Apply default values for any unset fields."""
        ...

    @property
    def service_config(self) -> ServiceConfig:
        """Return the base service configuration."""
        ...


@dataclass
class DefaultAppConfig:
    """Default AppConfig implementation for simple use cases.

    This replaces the previous AppConfig dataclass. Existing code that creates
    AppConfig(name="x", ...) should migrate to DefaultAppConfig.
    """

    service: ServiceConfig = field(default_factory=ServiceConfig)
    graceful_timeout: float = 30.0

    def apply_defaults(self) -> None:
        """Apply default values for any unset fields."""
        if not self.service.name:
            object.__setattr__(
                self,
                "service",
                ServiceConfig(
                    name="unknown",
                    environment=self.service.environment,
                    version=self.service.version,
                    debug=self.service.debug,
                    logging=self.service.logging,
                ),
            )

    @property
    def service_config(self) -> ServiceConfig:
        """Return the base service configuration."""
        return self.service

    # Convenience properties for backward compatibility

    @property
    def name(self) -> str:
        """Service name."""
        return self.service.name

    @property
    def version(self) -> str:
        """Service version."""
        return self.service.version

    @property
    def env(self) -> str:
        """Environment as a string value."""
        return self.service.environment.value

    @property
    def debug(self) -> bool:
        """Whether debug mode is enabled."""
        return self.service.debug

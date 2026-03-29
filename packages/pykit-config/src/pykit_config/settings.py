"""BaseSettings — Pydantic settings with env + TOML file support."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings as PydanticBaseSettings
from pydantic_settings import SettingsConfigDict


class BaseSettings(PydanticBaseSettings):
    """Base configuration class for all pykit services.

    Supports:
    - Environment variables (highest priority)
    - .env files
    - TOML config files (lowest priority)

    Subclass and add service-specific fields.
    """

    model_config = SettingsConfigDict(
        env_prefix="",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # Common settings for all services
    service_name: str = "pykit-service"
    environment: str = Field(
        default="development", description="development | staging | production"
    )
    host: str = "0.0.0.0"
    port: int = 50051
    log_level: str = "INFO"
    log_format: str = Field(default="auto", description="auto | json | console")
    metrics_port: int = 9090
    metrics_enabled: bool = True

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

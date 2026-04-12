"""BaseSettings — Pydantic settings with env + TOML file support."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Self

from pydantic import Field
from pydantic_settings import BaseSettings as PydanticBaseSettings
from pydantic_settings import SettingsConfigDict


class BaseSettings(PydanticBaseSettings):
    """Base configuration class for all pykit services.

    Supports:
    - Environment variables (highest priority)
    - .env files
    - Profile-specific env files (config/profiles/{profile}.env)
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
    environment: str = Field(default="development", description="development | staging | production")
    service_address: str = "0.0.0.0"
    service_port: int = 50051
    log_level: str = "INFO"
    log_format: str = Field(default="auto", description="auto | json | console")
    metrics_port: int = 9090
    metrics_enabled: bool = True

    @classmethod
    def with_profile(cls, profile: str | None = None, **kwargs: Any) -> Self:
        """Create settings with profile-specific env file loading.

        Args:
            profile: Profile name (e.g., "development", "docker", "staging").
                     If None, reads from ENVIRONMENT env var.
            **kwargs: Additional keyword arguments passed to the constructor.

        Returns:
            Settings instance with profile env file loaded.
        """
        if profile is None:
            profile = os.environ.get("ENVIRONMENT", "")

        if profile:
            profile_paths = [
                Path(f"./config/profiles/{profile}.env"),
                Path(f"../config/profiles/{profile}.env"),
                Path(f"../../config/profiles/{profile}.env"),
            ]
            for path in profile_paths:
                if path.exists():
                    from dotenv import load_dotenv

                    load_dotenv(path, override=False)
                    break

        return cls(**kwargs)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

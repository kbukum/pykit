"""Configuration loader — TOML files + environment variable overrides."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel as _PydanticBaseModel


def _has_custom_method(obj: object, name: str) -> bool:
    """Return True if *name* is defined on a class before pydantic's BaseModel in the MRO."""
    for cls in type(obj).__mro__:
        if cls is _PydanticBaseModel:
            return False
        if name in cls.__dict__:
            return True
    return False


def load_config[T](config_cls: type[T], path: str | Path = "config.toml", profile: str | None = None) -> T:
    """Load configuration from TOML file and environment variables.

    Priority: env vars > .env > profile env > TOML file > defaults.
    Environment variables use ``APP_`` prefix with ``__`` for nesting.

    Args:
        config_cls: The configuration class to instantiate.
        path: Path to the TOML config file. Ignored if it does not exist.
        profile: Configuration profile name (e.g., "development", "docker").
                 If None, no profile is loaded.
                 If empty string, reads from ENVIRONMENT env var.

    Returns:
        An instance of *config_cls* populated from file and env.
    """
    import tomllib

    # 0. Load profile env file first (lowest priority among env sources)
    if profile is not None:
        if not profile:
            profile = os.environ.get("ENVIRONMENT", "")
        if profile:
            profile_paths = [
                Path(f"./config/profiles/{profile}.env"),
                Path(f"../config/profiles/{profile}.env"),
                Path(f"../../config/profiles/{profile}.env"),
            ]
            for p in profile_paths:
                if p.exists():
                    from dotenv import load_dotenv

                    load_dotenv(p, override=False)
                    break

    data: dict[str, Any] = {}
    config_path = Path(path)

    # 1. Load from TOML file if it exists
    if config_path.exists():
        with config_path.open("rb") as f:
            data = tomllib.load(f)

    # 2. Override with env vars (APP_ prefix)
    prefix = os.environ.get("APP_CONFIG_PREFIX", "APP_")
    for key, value in os.environ.items():
        if key.startswith(prefix):
            # Convert APP_SERVICE__NAME to nested dict {"service": {"name": value}}
            parts = key[len(prefix) :].lower().split("__")
            d = data
            for part in parts[:-1]:
                d = d.setdefault(part, {})
            d[parts[-1]] = value

    # 3. Construct config
    config = config_cls(**data) if data else config_cls()

    # 4. Call apply_defaults if available
    if _has_custom_method(config, "apply_defaults"):
        config.apply_defaults()  # type: ignore[attr-defined]

    # 5. Call validate if available (skip pydantic's own classmethod)
    if _has_custom_method(config, "validate"):
        config.validate()  # type: ignore[attr-defined]

    return config

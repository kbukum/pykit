"""Configuration loader — TOML files + environment variable overrides."""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel as _PydanticBaseModel


def _has_custom_method(obj: object, name: str) -> bool:
    """Return True if *name* is defined on a class before pydantic's BaseModel in the MRO."""
    for cls in type(obj).__mro__:
        if cls is _PydanticBaseModel:
            return False
        if name in cls.__dict__:
            return True
    return False


def load_config[T](config_cls: type[T], path: str | Path = "config.toml") -> T:
    """Load configuration from TOML file and environment variables.

    Priority: env vars > TOML file > defaults.
    Environment variables use ``APP_`` prefix with ``__`` for nesting.

    Args:
        config_cls: The configuration class to instantiate.
        path: Path to the TOML config file. Ignored if it does not exist.

    Returns:
        An instance of *config_cls* populated from file and env.
    """
    import tomllib

    data: dict = {}
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
        config.apply_defaults()

    # 5. Call validate if available (skip pydantic's own classmethod)
    if _has_custom_method(config, "validate"):
        config.validate()

    return config

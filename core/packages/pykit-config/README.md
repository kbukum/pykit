# pykit-config

Configuration framework with TOML file loading, environment variable overrides, and Pydantic-based settings.

## Installation

```bash
pip install pykit-config
# or
uv add pykit-config
```

## Quick Start

```python
from dataclasses import dataclass
from pykit_config import load_config, BaseSettings

# Option 1: load_config() with any dataclass — TOML + env vars
@dataclass
class MyConfig:
    service: dict = None
    debug: bool = False

# Reads config.toml, then overrides with APP_* env vars
# APP_SERVICE__NAME=my-app  →  {"service": {"name": "my-app"}}
cfg = load_config(MyConfig, path="config.toml")

# Option 2: BaseSettings with Pydantic validation
class Settings(BaseSettings):
    service_name: str = "my-service"
    environment: str = "development"
    service_port: int = 50051
    log_level: str = "INFO"

settings = Settings()  # auto-reads env vars + .env files
print(settings.is_production)  # False
```

## Key Components

- **load_config(config_cls, path, profile)** — Generic config loader: reads TOML file, applies `APP_*` environment variable overrides (nested via `__` separator), calls optional `apply_defaults()` and `validate()` hooks; prefix customizable via `APP_CONFIG_PREFIX` env var
- **BaseSettings** — Extends `pydantic_settings.BaseSettings` with built-in fields for microservices: `service_name`, `environment`, `service_address`, `service_port`, `log_level`, `log_format`, `metrics_port`, `metrics_enabled`; includes `is_production` and `is_development` properties

### Loading Order (lowest → highest priority)

1. Class defaults
2. TOML config file
3. Profile env file (`config/profiles/{profile}.env`)
4. `APP_*` environment variables (for `load_config()`) / bare env vars (for `BaseSettings`)

### BaseSettings Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `service_name` | `str` | `"pykit-service"` | Service name |
| `environment` | `str` | `"development"` | Deployment environment |
| `service_address` | `str` | `"0.0.0.0"` | Service bind address |
| `service_port` | `int` | `50051` | Service port |
| `log_level` | `str` | `"INFO"` | Minimum log level |
| `log_format` | `str` | `"auto"` | Log format: auto, json, console |
| `metrics_port` | `int` | `9090` | Metrics endpoint port |
| `metrics_enabled` | `bool` | `True` | Enable metrics |

### Profile Support

```python
# load_config with profile
cfg = load_config(MyConfig, path="config.toml", profile="docker")

# BaseSettings with profile
settings = Settings.with_profile("docker")
```

### Validation Hooks

`load_config()` calls `apply_defaults()` then `validate()` on the config instance if defined.

## Dependencies

- `pydantic` — Data validation
- `pydantic-settings` — Environment-aware settings

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

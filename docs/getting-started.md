# Getting Started with pykit

## Prerequisites

- Python **3.13+**
- [uv](https://docs.astral.sh/uv/) package manager

## Installation

### Install the facade (all packages)

```bash
pip install pykit
# or
uv add pykit
```

### Install only what you need

```bash
uv add pykit-config pykit-logging pykit-resilience
```

## Quickstart Example

```python
from pykit_config import ServiceConfig, load_config
from pykit_logging import setup_logging, get_logger
from pykit_resilience import retry, CircuitBreaker

# Load typed config from environment or YAML
config = load_config(ServiceConfig, config_file="config.yml")
setup_logging(config)
log = get_logger("my-service")

# Resilient remote call
cb = CircuitBreaker(max_failures=5, timeout=30.0)

@retry(max_attempts=3, backoff=0.1)
async def fetch_data(url: str) -> dict:
    async with cb:
        ...  # your HTTP call here

async def main() -> None:
    log.info("starting", service=config.service_name)
    data = await fetch_data("https://api.example.com/data")
    log.info("done", rows=len(data))
```

## Development Setup

```bash
git clone https://github.com/kbukum/pykit.git
cd pykit
uv sync
uv run pytest packages/
```

## Common Package Combinations

| Use case | Packages |
|----------|----------|
| Web service foundation | `pykit-config` + `pykit-logging` + `pykit-errors` |
| gRPC service | above + `pykit-server` + `pykit-grpc` |
| Database access | `pykit-database` + `pykit-resilience` |
| Auth + authz | `pykit-auth` + `pykit-authz` |
| AI agent | `pykit-llm` + `pykit-tool` + `pykit-agent` |
| Observable service | `pykit-observability` + `pykit-observability` |

## Next Steps

- [Architecture overview](architecture.md) — understand the layer model
- [Package catalog](PACKAGES.md) — all 55 packages with descriptions
- [Contributing guide](../CONTRIBUTING.md) — how to contribute
- [Changelog](../CHANGELOG.md) — what's changed

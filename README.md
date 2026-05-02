# pykit

[![CI](https://github.com/kbukum/pykit/actions/workflows/ci.yml/badge.svg)](https://github.com/kbukum/pykit/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**A modular Python infrastructure library for building production services.** Config, structured logging, resilience, observability, dependency injection, async messaging, and AI tooling — packaged as 50+ independently installable sub-packages.

> **Status — pre-1.0.** All packages currently version together at `0.1.x`. Public surface follows semver; breaking changes are listed in [`CHANGELOG.md`](CHANGELOG.md). See [`docs/policy/SEMVER.md`](docs/policy/SEMVER.md).

> **Sibling projects.** [**gokit**](https://github.com/kbukum/gokit) (Go) · [**rskit**](https://github.com/kbukum/rskit) (Rust) · pykit (Python, this repo). Public abstractions (`AppError`, `Component`, `Provider`, `Pipeline`, lifecycle hooks) are evaluated for parity across all three.

## Highlights

- **uv workspace** — facade package (`pykit`) + 50+ independent `pykit-*` sub-packages. Install only what you need or use the facade.
- **Layered design** — Foundation → Core → Data & Flow → Infrastructure → Specialist. Lower layers never import higher ones, enforced via `import-linter`.
- **Python idioms** — `Protocol` classes, `async`/`await` throughout, Pydantic models, structlog.
- **Lifecycle-managed components** — uniform `Component` protocol (start / stop / health) and `pykit-bootstrap` orchestrator with graceful shutdown.
- **Production resilience** — circuit breaker, retry, bulkhead, rate limiter, timeout; OpenTelemetry tracing & metrics.
- **Sibling parity** — APIs mirror [gokit](https://github.com/kbukum/gokit) (Go) and [rskit](https://github.com/kbukum/rskit) (Rust).

## Install

```bash
# Facade (lazy-loads all sub-packages)
pip install pykit
# or
uv add pykit

# Or install just what you need
uv add pykit-config pykit-logging pykit-resilience
```

Requires **Python 3.13+**.

## Quickstart

```python
from pykit_config import ServiceConfig, load_config
from pykit_logging import setup_logging, get_logger
from pykit_resilience import retry, CircuitBreaker

config = load_config(ServiceConfig, config_file="config.yml")
setup_logging(config)
log = get_logger("my-service")

cb = CircuitBreaker(max_failures=5, timeout=30.0)

@retry(max_attempts=3, backoff=0.1)
async def fetch_data():
    async with cb:
        return await client.get("https://api.example.com/data")

log.info("service ready", env=config.environment)
```

More examples → [`docs/EXAMPLES.md`](docs/EXAMPLES.md). Full package list → [`docs/PACKAGES.md`](docs/PACKAGES.md).

## Development

```bash
# Install uv (https://docs.astral.sh/uv/)
curl -LsSf https://astral.sh/uv/install.sh | sh

uv sync         # sync workspace
uv run pytest   # run tests
uv run ruff check && uv run ruff format --check  # lint + format
```

## Documentation

| Topic | Link |
|---|---|
| All packages | [`docs/PACKAGES.md`](docs/PACKAGES.md) |
| Security model | [`docs/security-model.md`](docs/security-model.md) |
| Usage examples | [`docs/EXAMPLES.md`](docs/EXAMPLES.md) |
| Architecture decisions | [`docs/adr/`](docs/adr/) |
| Versioning & releases | [`docs/VERSIONING.md`](docs/VERSIONING.md) · [`docs/RELEASING.md`](docs/RELEASING.md) |
| Semver & deprecation policy | [`docs/policy/SEMVER.md`](docs/policy/SEMVER.md) · [`docs/policy/DEPRECATION.md`](docs/policy/DEPRECATION.md) |
| Cross-package integration | [`INTEGRATION.md`](INTEGRATION.md) |

## Contributing

We welcome contributions. See [`CONTRIBUTING.md`](CONTRIBUTING.md) for setup, code style, testing, and the PR process. By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

Other community docs: [`SECURITY.md`](SECURITY.md) · [`GOVERNANCE.md`](GOVERNANCE.md) · [`MAINTAINERS.md`](MAINTAINERS.md)

## License

[MIT](LICENSE)

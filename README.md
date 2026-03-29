# pykit — Python Infrastructure Library

> Standalone Python infrastructure library mirroring **gokit** (Go) and **rskit** (Rust).

## Quick Start

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync workspace
uv sync

# Run tests
uv run pytest
```

## Structure

pykit is a **uv workspace** with independent packages under `packages/`:

| Package | Description |
|---------|-------------|
| `pykit-errors` | Standard error types with gRPC status mapping |
| `pykit-config` | Configuration framework (Pydantic Settings) |
| `pykit-logging` | Structured logging (structlog) |
| `pykit-provider` | Provider protocols (request/response, stream, sink, duplex) |
| `pykit-pipeline` | Composable, pull-based async data pipelines |
| `pykit-server` | gRPC server bootstrap, health, interceptors |
| `pykit-metrics` | Prometheus metrics helpers |
| `pykit-testutil` | Test utilities for gRPC services |
| `pykit-triton` | Triton Inference Server client |
| `pykit-dataset` | Dataset collection, transformation, publishing |
| `pykit-bench` | Generic accuracy benchmarking framework |

## Principles

- **Same module names, same patterns** across gokit/rskit/pykit
- **Python idioms**: Protocol, async/await, Pydantic, structlog
- **Strict layering**: lower layers never import higher layers
- **Zero unnecessary coupling**: each package declares only its real dependencies

## License

MIT

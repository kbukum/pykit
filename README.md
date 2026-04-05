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

**Facade**

| Package | Description |
|---------|-------------|
| `pykit` | Lazy-loading facade that re-exports all sub-packages |

**Foundation**

| Package | Description |
|---------|-------------|
| `pykit-errors` | Standard error types with gRPC status mapping |
| `pykit-config` | Configuration framework (Pydantic Settings) |
| `pykit-logging` | Structured logging (structlog) |
| `pykit-validation` | Input validation utilities |
| `pykit-encryption` | Encryption and cryptographic utilities |
| `pykit-util` | Common utility functions |
| `pykit-version` | Version information and compatibility |
| `pykit-media` | Media type detection and handling |

**Core**

| Package | Description |
|---------|-------------|
| `pykit-provider` | Provider protocols (request/response, stream, sink, duplex) |
| `pykit-component` | Component lifecycle protocol (start/stop/health) |
| `pykit-bootstrap` | Application bootstrap and service wiring |
| `pykit-resilience` | Retry, circuit breaker, timeout patterns |
| `pykit-di` | Dependency injection container |
| `pykit-observability` | OpenTelemetry tracing and observability |
| `pykit-security` | Security utilities and policies |

**Data & Flow**

| Package | Description |
|---------|-------------|
| `pykit-pipeline` | Composable, pull-based async data pipelines |
| `pykit-dag` | Directed acyclic graph execution engine |
| `pykit-worker` | Background worker and task processing |
| `pykit-sse` | Server-Sent Events support |
| `pykit-stateful` | Stateful processing and state management |

**Infrastructure**

| Package | Description |
|---------|-------------|
| `pykit-database` | Async database access (SQLAlchemy + asyncpg) |
| `pykit-redis` | Redis client and caching utilities |
| `pykit-storage` | Object/file storage abstraction |
| `pykit-messaging` | Message broker abstraction with Kafka provider and in-memory broker for testing |
| `pykit-kafka-middleware` | Messaging middleware (dead-letter, retry, metrics, tracing) |
| `pykit-httpclient` | Async HTTP client (httpx) |

**Servers**

| Package | Description |
|---------|-------------|
| `pykit-server` | gRPC server bootstrap, health, interceptors |
| `pykit-server-middleware` | Server middleware (logging, auth, metrics) |
| `pykit-grpc` | gRPC client utilities and helpers |

**Security**

| Package | Description |
|---------|-------------|
| `pykit-auth` | Authentication (JWT validation, token handling) |
| `pykit-auth-oidc` | OpenID Connect authentication provider |
| `pykit-authz` | Authorization policies and RBAC |

**AI / ML**

| Package | Description |
|---------|-------------|
| `pykit-llm` | LLM client abstraction and prompt management |
| `pykit-triton` | Triton Inference Server client |
| `pykit-embedding` | Text/vector embedding utilities |
| `pykit-vector-store` | Vector store abstraction for similarity search |

**Platform**

| Package | Description |
|---------|-------------|
| `pykit-discovery` | Service discovery (Consul integration) |
| `pykit-metrics` | Prometheus metrics helpers |
| `pykit-process` | Process management utilities |
| `pykit-workload` | Workload scheduling and management |

**Testing & Data**

| Package | Description |
|---------|-------------|
| `pykit-testutil` | Test utilities for gRPC services |
| `pykit-dataset` | Dataset collection, transformation, publishing |
| `pykit-bench` | Generic accuracy benchmarking framework |

## Principles

- **Same module names, same patterns** across gokit/rskit/pykit
- **Python idioms**: Protocol, async/await, Pydantic, structlog
- **Strict layering**: lower layers never import higher layers
- **Zero unnecessary coupling**: each package declares only its real dependencies

## License

MIT

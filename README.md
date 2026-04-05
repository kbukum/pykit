# pykit — Python Infrastructure Library

[![CI](https://github.com/kbukum/pykit/actions/workflows/ci.yml/badge.svg)](https://github.com/kbukum/pykit/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

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
| `pykit-errors` | Standard error types with error codes, gRPC status mapping, and RFC 7807 support |
| `pykit-config` | Configuration framework using Pydantic Settings with environment variable support |
| `pykit-logging` | Structured logging with structlog integration |
| `pykit-validation` | Input validation utilities |
| `pykit-encryption` | Encryption and cryptographic utilities |
| `pykit-util` | Common utility functions — pure Python, zero dependencies |
| `pykit-version` | Version information and compatibility |
| `pykit-media` | Media type detection and handling |

**Core**

| Package | Description |
|---------|-------------|
| `pykit-provider` | Provider protocols for request/response, stream, sink, and duplex patterns |
| `pykit-component` | Component lifecycle protocol — start, stop, health |
| `pykit-bootstrap` | Application bootstrap and service wiring with lifecycle management |
| `pykit-resilience` | Retry, circuit breaker, bulkhead, rate limiter, and timeout patterns |
| `pykit-di` | Dependency injection container with eager, lazy, and singleton modes |
| `pykit-observability` | OpenTelemetry tracing, metrics, and context propagation |
| `pykit-security` | Security utilities and policies |

**Data & Flow**

| Package | Description |
|---------|-------------|
| `pykit-pipeline` | Composable, pull-based async data pipelines |
| `pykit-dag` | DAG execution engine with parallel task orchestration |
| `pykit-worker` | Background worker and task processing |
| `pykit-sse` | Server-Sent Events support |
| `pykit-stateful` | Stateful processing and state management |

**Infrastructure**

| Package | Description |
|---------|-------------|
| `pykit-database` | Async database access with SQLAlchemy and asyncpg |
| `pykit-redis` | Redis client and caching utilities with component lifecycle |
| `pykit-storage` | Object/file storage abstraction — local and S3 backends |
| `pykit-messaging` | Transport-agnostic messaging abstractions with Kafka provider |
| `pykit-kafka-middleware` | Messaging middleware — dead-letter, retry, metrics, tracing |
| `pykit-httpclient` | Async HTTP client with httpx and resilience patterns |

**Servers**

| Package | Description |
|---------|-------------|
| `pykit-server` | gRPC server bootstrap, health, and interceptors |
| `pykit-server-middleware` | Server middleware — logging, auth, metrics |
| `pykit-grpc` | gRPC client utilities and helpers |

**Security**

| Package | Description |
|---------|-------------|
| `pykit-auth` | JWT authentication and password hashing |
| `pykit-auth-oidc` | OpenID Connect authentication provider |
| `pykit-authz` | Authorization policies and RBAC |

**AI / ML**

| Package | Description |
|---------|-------------|
| `pykit-llm` | LLM client abstraction and prompt management |
| `pykit-triton` | Triton Inference Server client |
| `pykit-embedding` | Text and vector embedding utilities |
| `pykit-vector-store` | Vector store abstraction for similarity search |

**Platform**

| Package | Description |
|---------|-------------|
| `pykit-discovery` | Service discovery with Consul integration and load balancing |
| `pykit-metrics` | Prometheus metrics helpers |
| `pykit-process` | Process management utilities |
| `pykit-workload` | Workload scheduling and management |

**Testing & Data**

| Package | Description |
|---------|-------------|
| `pykit-testutil` | Test utilities for gRPC services |
| `pykit-dataset` | Dataset collection, transformation, and publishing |
| `pykit-bench` | Generic accuracy benchmarking framework |

## Principles

- **Same module names, same patterns** across gokit/rskit/pykit
- **Python idioms**: Protocol, async/await, Pydantic, structlog
- **Strict layering**: lower layers never import higher layers
- **Zero unnecessary coupling**: each package declares only its real dependencies

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for
development setup, code style, testing, and pull request guidelines.

This project follows the
[Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)
code of conduct.

## License

[MIT](LICENSE)

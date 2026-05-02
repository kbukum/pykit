# pykit Package Map

pykit is a **uv workspace** with a facade package and 50+ independent sub-packages under `packages/`. Every package has its own `README.md` — start there for API details. This file is the bird's-eye index.

## Facade

| Package | Description |
|---------|-------------|
| `pykit` | Lazy-loading facade that re-exports all sub-packages |

## Foundation

| Package | Description |
|---------|-------------|
| `pykit-errors` | Standard error types with error codes, gRPC status mapping, RFC 7807 |
| `pykit-config` | Configuration framework using Pydantic Settings |
| `pykit-logging` | Structured logging with structlog integration |
| `pykit-validation` | Input validation utilities |
| `pykit-encryption` | Encryption and cryptographic utilities |
| `pykit-util` | Common utility functions — pure Python, zero dependencies |
| `pykit-version` | Version information and compatibility |
| `pykit-media` | Media type detection and handling |

## Core

| Package | Description |
|---------|-------------|
| `pykit-provider` | Provider protocols (request/response, stream, sink, duplex) |
| `pykit-component` | Component lifecycle protocol — start, stop, health |
| `pykit-bootstrap` | Application bootstrap and service wiring with lifecycle |
| `pykit-resilience` | Retry, circuit breaker, bulkhead, rate limiter, timeout |
| `pykit-di` | Dependency injection container (eager, lazy, singleton) |
| `pykit-observability` | OpenTelemetry tracing, metrics, context propagation |
| `pykit-security` | Security utilities and policies |

## Data & Flow

| Package | Description |
|---------|-------------|
| `pykit-pipeline` | Composable, pull-based async data pipelines |
| `pykit-dag` | DAG execution engine with parallel task orchestration |
| `pykit-worker` | Background worker and task processing |
| `pykit-sse` | Server-Sent Events support with bounded client queues |
| `pykit-stateful` | Stateful processing and state management |

## Infrastructure

| Package | Description |
|---------|-------------|
| `pykit-database` | Async database access with SQLAlchemy and asyncpg |
| `pykit-cache` | cache client and caching utilities |
| `pykit-storage` | Object/file storage abstraction — local and S3 backends |
| `pykit-messaging` | Transport-agnostic messaging with Kafka provider |
| `pykit-messaging` | Messaging middleware — DLQ, retry, metrics, tracing |
| `pykit-httpclient` | Async HTTP client with bounded redirects and resilience integration |

## Servers

| Package | Description |
|---------|-------------|
| `pykit-server` | gRPC server bootstrap plus folded HTTP middleware and interceptor ordering |
| `pykit-grpc` | gRPC transport utilities and helpers |

## Security

| Package | Description |
|---------|-------------|
| `pykit-auth` | JWT, API key, OIDC, and password authentication primitives |
| `pykit-authz` | Default-deny RBAC + ABAC authorization engine |
| `pykit-security` | TLS, secure headers, CORS, and token extraction policies |

## AI / ML

| Package | Description |
|---------|-------------|
| `pykit-llm` | LLM client abstraction and prompt management |
| `pykit-llm-providers` | LLM provider implementations — OpenAI, Anthropic, Gemini |
| `pykit-inference` | Triton Inference Server client |
| `pykit-embedding` | Text and vector embedding utilities |
| `pykit-vectorstore` | Vector store abstraction for similarity search |
| `pykit-agent` | Agentic loop — LLM orchestration, tool execution |
| `pykit-tool` | Tool definitions, auto-wiring, registry, middleware |
| `pykit-hook` | Generic event hook system |
| `pykit-mcp` | Model Context Protocol server and client bridge |
| `pykit-schema` | JSON Schema generation and validation |
| `pykit-explain` | Structured explanation generation via LLM |

## Platform

| Package | Description |
|---------|-------------|
| `pykit-discovery` | Service discovery with resilience-backed self-registration |
| `pykit-observability` | Prometheus metrics helpers |
| `pykit-process` | Process management utilities |
| `pykit-workload` | Workload scheduling and management |

## Testing & Data

| Package | Description |
|---------|-------------|
| `pykit-testutil` | Test utilities for gRPC services |
| `pykit-dataset` | Dataset collection, transformation, publishing |
| `pykit-bench` | Generic accuracy benchmarking framework |

See [`docs/architecture.md`](architecture.md) for the current layering rationale.

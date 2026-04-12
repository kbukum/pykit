# pykit — Python Infrastructure Library

[![CI](https://github.com/kbukum/pykit/actions/workflows/ci.yml/badge.svg)](https://github.com/kbukum/pykit/actions/workflows/ci.yml)
[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> Standalone Python infrastructure library mirroring **gokit** (Go) and **rskit** (Rust).

## Architecture Overview

pykit is a **uv workspace** with a facade package and 50+ independent sub-packages under `packages/`:

- **Facade package** (`pykit`) — lazy-loading re-export of all sub-packages. Import only what you need or use the facade.
- **Sub-packages** (`pykit-{name}`) — each has its own `pyproject.toml`, installs independently. Dependencies flow strictly downward.
- **Layered design** — Foundation → Core → Data & Flow → Infrastructure → Specialist. Lower layers never import higher layers.
- **Python idioms** — Protocol classes, async/await, Pydantic models, structlog logging.

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
| `pykit-llm-providers` | LLM provider implementations — OpenAI, Anthropic, Gemini |
| `pykit-triton` | Triton Inference Server client |
| `pykit-embedding` | Text and vector embedding utilities |
| `pykit-vector-store` | Vector store abstraction for similarity search |
| `pykit-agent` | Agentic loop — LLM orchestration, tool execution, context management |
| `pykit-tool` | Tool definitions, auto-wiring, registry, and middleware |
| `pykit-hook` | Generic event hook system for lifecycle handler registration |
| `pykit-mcp` | Model Context Protocol server and client bridge |
| `pykit-schema` | JSON Schema generation and validation from Python types |
| `pykit-explain` | Structured explanation generation from analysis signals via LLM |

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

## Usage Examples

### Config + Logging

```python
from pykit_config import ServiceConfig, load_config
from pykit_logging import setup_logging, get_logger

config = load_config(ServiceConfig, config_file="config.yml")
setup_logging(config)
log = get_logger("my-service")
log.info("service configured", env=config.environment)
```

### Resilience Patterns

```python
from pykit_resilience import retry, CircuitBreaker

cb = CircuitBreaker(max_failures=5, timeout=30.0)

@retry(max_attempts=3, backoff=0.1)
async def call_external():
    async with cb:
        return await httpx.get("https://api.example.com/data")
```

### Agent Loop

```python
from pykit_agent import Agent, AgentConfig
from pykit_tool import Registry

registry = Registry()
registry.register(weather_tool)

agent = Agent(llm_provider, registry, config=AgentConfig(max_turns=10))
result = await agent.run("What's the weather in Berlin?")
print(result.events)
```

### LLM Chat Completion

```python
from pykit_llm import LLMProvider, Request, Message

provider = LLMProvider(dialect="openai", model="gpt-4", api_key=os.getenv("OPENAI_API_KEY"))
resp = await provider.chat_completion(Request(
    messages=[Message(role="user", content="Explain circuit breakers")],
))
print(resp.content)
```

### Messaging

```python
from pykit_messaging import Producer, Consumer

producer = Producer(config)
await producer.publish("events", key="user-123", value=payload)

consumer = Consumer(config, group="my-group")
consumer.subscribe("events", handler=process_event)
await consumer.start()
```

### Object Storage

```python
from pykit_storage import Storage

store = Storage(config)
await store.put("uploads/report.pdf", data)
content = await store.get("uploads/report.pdf")
```

## Cross-Kit Comparison

pykit, [gokit](https://github.com/kbukum/gokit) (Go), and [rskit](https://github.com/kbukum/rskit) (Rust) share the same module structure and design philosophy. The table below shows capability coverage across all three kits.

| Capability | gokit | rskit | pykit |
|---|---|---|---|
| Errors | ✅ `errors` | ✅ `rskit-errors` | ✅ `pykit-errors` |
| Config | ✅ `config` | ✅ `rskit-config` | ✅ `pykit-config` |
| Logging | ✅ `logger` | ✅ `rskit-logging` | ✅ `pykit-logging` |
| Validation | ✅ `validation` | ✅ `rskit-validation` | ✅ `pykit-validation` |
| Encryption | ✅ `encryption` | ✅ `rskit-encryption` | ✅ `pykit-encryption` |
| Utilities | ✅ `util` | ❌ | ✅ `pykit-util` |
| Version | ✅ `version` | ❌ | ✅ `pykit-version` |
| Media | ✅ `media` | ✅ `rskit-media` | ✅ `pykit-media` |
| Security | ✅ `security` | ❌ | ✅ `pykit-security` |
| DI | ✅ `di` | ✅ `rskit-di` | ✅ `pykit-di` |
| Component | ✅ `component` | ❌ | ✅ `pykit-component` |
| Bootstrap | ✅ `bootstrap` | ✅ `rskit-bootstrap` | ✅ `pykit-bootstrap` |
| Provider | ✅ `provider` | ✅ `rskit-provider` | ✅ `pykit-provider` |
| Resilience | ✅ `resilience` | ✅ `rskit-resilience` | ✅ `pykit-resilience` |
| Observability | ✅ `observability` | ✅ `rskit-observability` | ✅ `pykit-observability` |
| Pipeline | ✅ `pipeline` | ✅ `rskit-pipeline` | ✅ `pykit-pipeline` |
| DAG | ✅ `dag` | ✅ `rskit-dag` | ✅ `pykit-dag` |
| Worker | ✅ `worker` | ✅ `rskit-worker` | ✅ `pykit-worker` |
| SSE | ✅ `sse` | ✅ `rskit-sse` | ✅ `pykit-sse` |
| Stateful | ✅ `stateful` | ❌ | ✅ `pykit-stateful` |
| Auth | ✅ `auth` | ✅ `rskit-auth` | ✅ `pykit-auth` |
| Authz | ✅ `authz` | ✅ `rskit-authz` | ✅ `pykit-authz` |
| Database | ✅ `database` | ✅ `rskit-database` | ✅ `pykit-database` |
| Redis / Cache | ✅ `redis` | ✅ `rskit-cache` | ✅ `pykit-redis` |
| Storage / File | ✅ `storage` | ✅ `rskit-file` | ✅ `pykit-storage` |
| Messaging | ✅ `messaging` | ✅ `rskit-messaging` | ✅ `pykit-messaging` |
| HTTP Client | ✅ `httpclient` | ✅ `rskit-httpclient` | ✅ `pykit-httpclient` |
| Server | ✅ `server` | ✅ `rskit-http`, `rskit-server` | ✅ `pykit-server` |
| gRPC Client | ✅ `grpc` | ✅ `rskit-grpc-client` | ✅ `pykit-grpc` |
| Connect | ✅ `connect` | ❌ | ❌ |
| Discovery | ✅ `discovery` | ✅ `rskit-discovery` | ✅ `pykit-discovery` |
| Process | ✅ `process` | ✅ `rskit-process` | ✅ `pykit-process` |
| Workload | ✅ `workload` | ❌ | ✅ `pykit-workload` |
| Test Utilities | ✅ `testutil` | ✅ `rskit-testutil` | ✅ `pykit-testutil` |
| LLM | ✅ `llm` | ✅ `rskit-llm` | ✅ `pykit-llm` |
| LLM Providers | ❌ | ✅ `rskit-llm-providers` | ✅ `pykit-llm-providers` |
| Agent | ✅ `agent` | ✅ `rskit-agent` | ✅ `pykit-agent` |
| Tool | ✅ `tool` | ✅ `rskit-tool` | ✅ `pykit-tool` |
| MCP | ✅ `mcp` | ✅ `rskit-mcp` | ✅ `pykit-mcp` |
| Hook | ✅ `hook` | ✅ `rskit-hook` | ✅ `pykit-hook` |
| Schema | ✅ `schema` | ✅ `rskit-schema` | ✅ `pykit-schema` |
| Explain | ✅ `explain` | ✅ `rskit-explain` | ✅ `pykit-explain` |
| Bench | ✅ `bench` | ✅ `rskit-bench` | ✅ `pykit-bench` |
| Dataset | ❌ | ✅ `rskit-dataset` | ✅ `pykit-dataset` |
| Embedding | ✅ `embedding` | ✅ `rskit-embedding` | ✅ `pykit-embedding` |
| Vector Store | ✅ `vectorstore` | ✅ `rskit-vector-store` | ✅ `pykit-vector-store` |
| Inference | ❌ | ✅ `rskit-inference` | ✅ `pykit-triton` |
| CLI | ❌ | ✅ `rskit-cli` | ❌ |
| Metrics | ❌ | ❌ | ✅ `pykit-metrics` |

## Contributing

We welcome contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for
development setup, code style, testing, and pull request guidelines.

This project follows the
[Contributor Covenant v2.1](https://www.contributor-covenant.org/version/2/1/code_of_conduct/)
code of conduct.

## License

[MIT](LICENSE)

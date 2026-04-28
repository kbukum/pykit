# pykit-logging

Production-ready structured logging built on [structlog](https://www.structlog.org/).

## Features

- Structured JSON / console output
- Sensitive data masking (**on by default**)
- Rate-based log sampling (burst + thereafter)
- Per-module log level overrides
- OpenTelemetry Logs bridge (OTLP export)
- Unified log schema (consistent across gokit, pykit, rskit)
- Correlation ID tracking for distributed tracing

## Installation

```bash
pip install pykit-logging

# With OTLP export support
pip install pykit-logging[otlp]
```

The `[otlp]` extra installs `opentelemetry-sdk`, `opentelemetry-exporter-otlp-proto-grpc`, and `opentelemetry-exporter-otlp-proto-http`.

## Quick Start

```python
from pykit_logging import setup_logging, get_logger

# Configure once at startup — masking is on by default
setup_logging(
    level="INFO",
    log_format="json",          # "json" | "console" | "auto" (TTY=console, non-TTY=json)
    service_name="my-service",
)

logger = get_logger("my_module")
logger.info("request processed", user_id="abc", duration_ms=42)

# Sensitive data is automatically redacted
logger.info("login", password="hunter2")
# output: password=***REDACTED***
```

## Configuration

`setup_logging()` accepts all options as keyword arguments:

```python
from pykit_logging import (
    setup_logging,
    shutdown_logging,
    MaskingConfig,
    SamplingConfig,
    OTLPConfig,
)

setup_logging(
    level="INFO",
    log_format="json",
    service_name="my-service",
    environment="production",

    # Masking — on by default
    masking=MaskingConfig(
        enabled=True,
        field_names=("my_secret_field",),
        value_patterns=(r"MYSECRET_[A-Z0-9]{20}",),
        replacement="***REDACTED***",
    ),

    # Sampling — off by default
    sampling=SamplingConfig(
        enabled=True,
        initial_rate=100,
        thereafter_rate=10,
    ),

    # Per-module overrides
    module_levels={
        "aiokafka": "CRITICAL",
        "httpx": "WARNING",
        "database": "DEBUG",
    },

    # OTLP export — off by default
    otlp=OTLPConfig(
        enabled=True,
        endpoint="http://localhost:4317",
        protocol="grpc",
        insecure=True,
    ),
)

# At shutdown — flush OTLP logs
shutdown_logging()
```

## Masking

Masking is **enabled by default**. Every log field is checked against sensitive field names (case-insensitive) and value patterns (regex). If a match is found, the value is replaced before it reaches any output sink or OTLP exporter.

### Default Masked Fields

| # | Field Name | Description |
|---|-----------|-------------|
| 1 | `password` | User passwords |
| 2 | `secret` | Generic secrets |
| 3 | `token` | Generic tokens |
| 4 | `api_key` | API keys |
| 5 | `apikey` | API keys (alternate) |
| 6 | `api-key` | API keys (hyphenated) |
| 7 | `authorization` | Auth headers |
| 8 | `auth_token` | Authentication tokens |
| 9 | `access_token` | OAuth access tokens |
| 10 | `refresh_token` | OAuth refresh tokens |
| 11 | `private_key` | Private keys |
| 12 | `ssn` | Social Security numbers |
| 13 | `credit_card` | Credit card numbers |
| 14 | `card_number` | Card numbers (alternate) |
| 15 | `cvv` | Card verification values |
| 16 | `pin` | Personal identification numbers |

### Value Patterns

These patterns detect sensitive data regardless of field name:

| # | Pattern | Example Input | Masked Output |
|---|---------|---------------|---------------|
| 1 | JWT | `eyJhbGci...payload...sig` | `[JWT_REDACTED]` |
| 2 | Bearer token | `Bearer abc123def` | `Bearer [REDACTED]` |
| 3 | AWS Access Key | `AKIAIOSFODNN7EXAMPLE` | `[AWS_KEY_REDACTED]` |
| 4 | Credit Card | `4111-1111-1111-1234` | `****-****-****-1234` |
| 5 | SSN | `123-45-6789` | `***-**-****` |
| 6 | Email | `user@example.com` | `***@***.***` |
| 7 | Hex Secret (32+) | `a1b2c3d4e5f6...` (32+ hex chars) | `[HEX_REDACTED]` |

### Adding Custom Fields and Patterns

```python
masking = MaskingConfig(
    field_names=("my_internal_token", "employee_id"),
    value_patterns=(r"MYSVC_[A-Za-z0-9]{32}",),
)
setup_logging(masking=masking, ...)
```

## Sampling

Sampling reduces log volume in high-throughput services. When enabled, each log level gets an independent counter per one-second window:

1. **Burst** — the first `initial_rate` messages per second per level pass through unconditionally.
2. **Thereafter** — after the burst, only every `thereafter_rate`-th message is kept.

```python
sampling = SamplingConfig(
    enabled=True,
    initial_rate=100,      # allow first 100/sec per level
    thereafter_rate=10,    # then keep every 10th
)
setup_logging(sampling=sampling, ...)
```

> **When to use:** Enable sampling on hot-path services producing thousands of log lines per second. Leave disabled for low-volume services or during debugging.

The sampler uses `time.monotonic()` for window tracking and is thread-safe. When a message is dropped, `structlog.DropEvent` is raised internally — the event is silently discarded.

## Module Levels

Override the global log level for specific logger names (matched by prefix). Useful for silencing noisy third-party libraries or enabling debug output for a single subsystem.

```python
setup_logging(
    level="INFO",
    module_levels={
        "aiokafka": "CRITICAL",    # suppress Kafka reconnection noise
        "httpx": "WARNING",        # reduce HTTP client verbosity
        "database": "DEBUG",       # verbose DB logs
    },
)
```

The processor matches against the `logger_name` or `_logger_name` field in each log event. Prefix matching is greedy — the longest matching prefix wins, so `"aiokafka.consumer"` can override `"aiokafka"` if both are present.

When an event's level is below the configured minimum for its module, `structlog.DropEvent` is raised.

## OTLP Export

The OpenTelemetry Logs bridge sends log records to an OTLP collector alongside your local output. The OTLP processor is inserted **after** the masking processor, so exported logs are already redacted.

### Setup

```python
from pykit_logging import setup_logging, shutdown_logging, OTLPConfig

setup_logging(
    service_name="my-service",
    environment="production",
    otlp=OTLPConfig(
        enabled=True,
        endpoint="http://otel-collector:4317",
        protocol="grpc",       # "grpc" | "http"
        insecure=True,         # skip TLS for dev
        headers={"Authorization": "Bearer my-token"},
    ),
)

# ... application runs ...

# Graceful shutdown — flush pending OTLP logs
shutdown_logging()
```

### Dependencies

OTLP requires optional packages. Install them with:

```bash
pip install pykit-logging[otlp]

# Or manually:
pip install opentelemetry-sdk \
    opentelemetry-exporter-otlp-proto-grpc \
    opentelemetry-exporter-otlp-proto-http
```

If the OTel packages are not installed and OTLP is enabled, a clear `ImportError` is raised with installation instructions.

### Trace Context

When an active OpenTelemetry span exists, the bridge automatically attaches `trace_id`, `span_id`, and `trace_flags` to exported log records — enabling log-to-trace correlation in your backend.

## Unified Schema

All three kits (gokit, pykit, rskit) share the same structured field names:

| Field | Description |
|-------|-------------|
| `service` | Service name |
| `environment` | Deployment environment |
| `version` | Service version |
| `component` | Logical component |
| `trace_id` | Distributed trace ID |
| `span_id` | Span ID within trace |
| `correlation_id` | Cross-service correlation |
| `user_id` | User identifier |
| `request_id` | HTTP request identifier |
| `duration_ms` | Duration in milliseconds |
| `timestamp` | ISO 8601 timestamp |
| `level` | Log level |

### Schema Normalizer

The `schema_normalizer` processor adds `service` and `environment` fields to every log entry:

```python
# Included automatically by setup_logging(), or use directly:
from pykit_logging import schema_normalizer

processor = schema_normalizer("order-svc", "production")
```

### Correlation IDs

```python
from pykit_logging.setup import set_correlation_id, new_correlation_id

# Generate and set a correlation ID for the current context
cid = set_correlation_id()

# Or use a specific ID (e.g., from an incoming request header)
set_correlation_id("abc-123-def")

# All subsequent log entries include correlation_id automatically
logger.info("handling request")
# → {"correlation_id": "abc-123-def", ...}
```

## Custom Masker

Implement the `Masker` protocol to provide your own masking logic:

```python
from pykit_logging import Masker, masking_processor

class MyMasker:
    def mask_value(self, key: str, value: str) -> str:
        if key == "internal_id":
            return "***"
        return value

# Use as a standalone structlog processor
processor = masking_processor(MyMasker())
```

## API Reference

| Function / Type | Description |
|----------------|-------------|
| `setup_logging(...)` | Configure structured logging (call once at startup) |
| `shutdown_logging()` | Flush OTLP logs and shut down |
| `get_logger(name)` | Get a `structlog.stdlib.BoundLogger` instance |
| `MaskingConfig` | Masking configuration (dataclass) |
| `DefaultMasker` | Built-in masker with PII/secret patterns |
| `Masker` | Protocol for custom maskers |
| `masking_processor(masker)` | Create a structlog masking processor |
| `SamplingConfig` | Sampling configuration (dataclass) |
| `LogSampler` | Rate-based sampler with per-level counters |
| `sampling_processor(config)` | Create a structlog sampling processor |
| `ModuleLevelsConfig` | Per-module level override config (dataclass) |
| `module_levels_processor(config)` | Create a structlog module-levels processor |
| `OTLPConfig` | OTLP export configuration (dataclass) |
| `OTLPLogBridge` | Bridge between structlog and OTel LoggerProvider |
| `otlp_processor(bridge)` | Create a structlog OTLP processor |
| `schema_normalizer(service, env)` | Create a structlog schema normalizer processor |
| `set_correlation_id(cid)` | Set correlation ID for current context |
| `new_correlation_id()` | Generate a UUID correlation ID |

## Dependencies

- `structlog` — Structured logging library

Optional (for OTLP):
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp-proto-grpc`
- `opentelemetry-exporter-otlp-proto-http`

---

[⬅ Back to main README](../../README.md)

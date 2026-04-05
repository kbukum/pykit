# pykit-kafka-middleware

Composable middleware for Kafka message handlers: retry, dead-letter queue, Prometheus metrics, and OpenTelemetry tracing.

## Installation

```bash
pip install pykit-kafka-middleware
# or
uv add pykit-kafka-middleware
```

## Quick Start

```python
from pykit_kafka_middleware import (
    RetryHandler, RetryMiddlewareConfig,
    DeadLetterProducer, InstrumentHandler, TracingHandler,
)

# Compose middleware around a message handler
async def process(msg: Message) -> None:
    print(f"Processing: {msg.key}")

# 1. Add retry with exponential backoff
config = RetryMiddlewareConfig(max_attempts=3, initial_backoff=0.1)
dlq = DeadLetterProducer(producer, suffix=".dlq")
config.on_exhausted = dlq.send  # route to DLQ after retries

handler = RetryHandler(process, config)

# 2. Add Prometheus metrics
handler = InstrumentHandler("orders", "order-group", handler)

# 3. Add distributed tracing
handler = TracingHandler(handler, tracer_name="kafka.consumer")
```

## Key Components

- **RetryHandler** — Wraps a `MessageHandler` with exponential backoff retry; configurable via `RetryMiddlewareConfig` with `max_attempts`, `initial_backoff`, `max_backoff`, `backoff_factor`, `jitter`, optional `retry_if` filter, and `on_exhausted` callback
- **RetryMiddlewareConfig** — Retry configuration dataclass; sets `x-retry-count` header on each attempt
- **DeadLetterProducer** — Sends failed messages to a dead-letter queue topic (`{topic}.dlq` by default); wraps messages in `DeadLetterEnvelope` with original topic, error, retry count, and timestamp
- **DeadLetterEnvelope** — DLQ message structure: `original_topic`, `error`, `retry_count`, `timestamp`, `headers`, `payload`
- **InstrumentHandler** — Prometheus metrics middleware recording `messages_total`, `errors_total`, and `processing_duration_seconds` with `topic` and `group` labels
- **TracingHandler** — OpenTelemetry distributed tracing; extracts/injects W3C TraceContext from message headers, creates consumer spans with messaging attributes

## Dependencies

- `pykit-messaging` — Message handler and producer protocols
- `pykit-resilience` — Resilience patterns
- `opentelemetry-api` — Distributed tracing
- `prometheus-client` — Metrics collection

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

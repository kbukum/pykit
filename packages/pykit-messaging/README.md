# pykit-messaging

Transport-agnostic messaging abstractions with optional Kafka, NATS, and RabbitMQ adapters, in-memory broker for testing, and middleware support.

## Installation

```bash
pip install pykit-messaging
# or
uv add pykit-messaging

# With Kafka, NATS, or RabbitMQ support
pip install pykit-messaging[kafka]
pip install pykit-messaging[nats]
pip install pykit-messaging[rabbitmq]

# With provider bridges (pykit-provider, pykit-pipeline, pykit-dag, pykit-worker)
pip install pykit-messaging[bridges]
```

## Quick Start

```python
from pykit_messaging import (
    InMemoryBroker, ManagedProducer, ManagedConsumer,
    FuncHandler, MessageRouter, Event,
    assert_published_n, wait_for_message,
)

# Testing: use InMemoryBroker directly.
broker = InMemoryBroker()
producer = broker.producer()
consumer = broker.consumer(["orders"])

await producer.send_event("orders", Event(type="order.created", source="shop", data={"id": 1}))

msg = await wait_for_message(broker, "orders", timeout=1.0)
assert_published_n(broker, "orders", 1)
```

### Adapter registration

Optional broker SDKs are never imported by `import pykit_messaging`. Adapter modules keep config in `config.py` and lazily import SDK clients at connection time with extra-specific install errors. Register adapters explicitly in composition code; registration is config-free and each producer/consumer creation receives the typed adapter config.

```python
from pykit_messaging import MessagingRegistry
from pykit_messaging.memory import register as register_memory
from pykit_messaging.kafka import KafkaConfig, register as register_kafka

registry = MessagingRegistry()
register_memory(registry)
register_kafka(registry)

producer = registry.producer(
    KafkaConfig(brokers=["kafka.internal:9093"], security_protocol="SSL")
)
await producer.start()
await producer.send("events", b'{"action": "click"}', key="user-1")
```

### Configuration model

`BrokerConfig` contains only broker-neutral policy: adapter selection, name/enabled flags,
delivery guarantee, commit strategy, DLQ policy, retry/request timeout settings,
`max_in_flight`, `consumer_group`, and adapter-neutral `topics`/`subscriptions`. Broker
endpoints, protocol security credentials, batching, compression, routing/exchange details,
and adapter-specific timeouts live in adapter configs such as `KafkaConfig`, `NatsConfig`,
`RabbitMqConfig`, and `MemoryConfig`. Kafka, NATS, and RabbitMQ SDKs stay isolated behind
optional extras; core and memory imports do not pull optional SDKs into the runtime graph.

Factories validate creation-time config. Unsupported shared semantics are rejected with
`AppError` instead of being silently ignored; for example, core NATS subjects reject ack-based
at-least-once/exactly-once settings, RabbitMQ requires `auto_ack` to match `commit_strategy`,
and Kafka does not support exactly-once delivery (at-least-once is the maximum guarantee).
Secure connection settings are the default (`SSL`, `tls://`, `amqps://`); plaintext development
endpoints require `allow_insecure_dev=True`. Credentials belong in typed fields or secret-managed
settings, never in broker URLs or examples.

### Handler Middleware

```python
from pykit_messaging import FuncHandler, chain_handlers, dedup, DedupConfig

base = FuncHandler(my_handler_func)
wrapped = chain_handlers(base, dedup(DedupConfig(window_size=100, ttl=60.0)))
```

## Key Components

- **MessageProducer / MessageConsumer** — Transport-agnostic protocols for sending and receiving messages
- **Message / Event** — Wire-format envelope and structured domain event types
- **ManagedProducer / ManagedConsumer** — Lifecycle wrappers with metrics and graceful shutdown
- **MessageRouter** — Topic-based handler dispatch with fnmatch wildcard patterns
- **BatchProducer** — Collects and flushes messages in size/time/byte-triggered batches
- **KafkaProducer / KafkaConsumer / KafkaComponent** — Optional Kafka implementation using aiokafka
- **NatsProducer / NatsConsumer** — Optional core NATS subject implementation using nats-py
- **RabbitMqProducer / RabbitMqConsumer** — Optional RabbitMQ implementation using aio-pika
- **InMemoryBroker** — In-memory broker for testing with bounded queues/history and assertion helpers
- **DeadLetterProducer / DeadLetterEnvelope** — Opt-in DLQ routing with canonical `original_topic`, `error`, `retry_count`, `timestamp`, `headers`, and `payload` fields plus redaction
- **DedupHandler / CircuitBreakerHandler** — Middleware for deduplication and circuit breaking
- **chain_handlers()** — Compose middleware around a base handler
- **assert_published() / wait_for_message()** — Test assertion helpers

`MemoryConfig.history_limit` bounds recorded assertion history (default `1024`) and `MemoryConfig.max_brokers`
bounds registry-owned in-memory brokers (default `32`). Use `clear_memory_brokers(registry)` in tests to
drop registry-owned brokers between scenarios.

## Dependencies

- `pykit-errors`, `pykit-component`
- Optional and isolated by extra: `aiokafka` (kafka), `nats-py` (nats), `aio-pika` (rabbitmq), `pykit-provider`, `pykit-pipeline`, `pykit-dag`, `pykit-worker` (bridges)

## Validation

Focused documentation checks verify that examples avoid hardcoded credentials and that core docs describe NATS/RabbitMQ as real opt-in adapters. Full validation counts belong to the CI/validation pass and are not claimed here.

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

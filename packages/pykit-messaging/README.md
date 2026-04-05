# pykit-messaging

Transport-agnostic messaging abstractions with Kafka provider, in-memory broker for testing, and middleware support.

## Installation

```bash
pip install pykit-messaging
# or
uv add pykit-messaging

# With Kafka support
pip install pykit-messaging[kafka]

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

# Production: use KafkaProducer / KafkaConsumer
# Testing: use InMemoryBroker
broker = InMemoryBroker()
producer = broker.producer()
consumer = broker.consumer(["orders"])

await producer.send_event("orders", Event(type="order.created", source="shop", data={"id": 1}))

msg = await wait_for_message(broker, "orders", timeout=1.0)
assert_published_n(broker, "orders", 1)
```

### Kafka Setup

```python
from pykit_messaging import KafkaConfig, KafkaComponent

config = KafkaConfig(name="my-app", brokers="localhost:9092")
component = KafkaComponent(config)
await component.start()

producer = component.producer
await producer.send("events", b'{"action": "click"}', key=b"user-1")
```

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
- **KafkaProducer / KafkaConsumer / KafkaComponent** — Concrete Kafka implementation using aiokafka
- **InMemoryBroker** — In-memory broker for testing with assertion helpers
- **DedupHandler / CircuitBreakerHandler** — Middleware for deduplication and circuit breaking
- **chain_handlers()** — Compose middleware around a base handler
- **assert_published() / wait_for_message()** — Test assertion helpers

## Dependencies

- `pykit-errors`, `pykit-component`
- Optional: `aiokafka` (kafka extra), `pykit-provider`, `pykit-pipeline`, `pykit-dag`, `pykit-worker` (bridges extra)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

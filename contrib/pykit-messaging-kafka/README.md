# pykit-messaging-kafka

Kafka adapter package for `pykit-messaging`.

## Installation

```bash
uv add pykit-messaging-kafka
# or
pip install pykit-messaging-kafka
```

## Quick start

```python
from pykit_messaging_kafka import KafkaConfig, KafkaProducer

producer = KafkaProducer(KafkaConfig(brokers=["localhost:9092"]))
await producer.start()
await producer.send("events", b'{"status":"ok"}', key="evt-1")
await producer.close()
```

## Registry wiring

Use `register(registry)` when your application selects messaging adapters through a `MessagingRegistry`.

```python
from pykit_messaging import MessagingRegistry
from pykit_messaging_kafka import KafkaConfig, register

registry = MessagingRegistry()
register(registry)

producer = registry.producer(KafkaConfig(brokers=["localhost:9092"]))
consumer = registry.consumer(KafkaConfig(topics=["events"]))
```

## What this package provides

- `KafkaProducer` and `KafkaConsumer`
- `KafkaComponent` for component-style lifecycle management
- `KafkaConfig` for adapter-specific settings
- `register(registry)` to register the `"kafka"` adapter explicitly
- Optional middleware and helpers, including retry, tracing, metrics, dead-letter support, and Kafka error classification

## Configuration highlights

- Secure connections are the default with `security_protocol="SSL"`.
- Plaintext protocols require `allow_insecure_dev=True`.
- Connection URLs with embedded credentials or query strings are rejected. Use typed SASL fields instead.
- `topics`, `group_id`, `consumer_group`, batching, compression, acks, retries, and timeouts are all configured through `KafkaConfig`.
- Exactly-once delivery is rejected by this adapter.

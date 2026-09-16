# pykit-messaging-rabbitmq

RabbitMQ adapter package for `pykit-messaging`.

## Installation

```bash
uv add pykit-messaging-rabbitmq
# or
pip install pykit-messaging-rabbitmq
```

## Quick start

```python
from pykit_messaging_rabbitmq import RabbitMqConfig, RabbitMqProducer

producer = RabbitMqProducer(
    RabbitMqConfig(
        url="amqp://localhost:5672/",
        allow_insecure_dev=True,
    )
)
await producer.send("events", b'{"status":"ok"}', key="evt-1")
await producer.close()
```

## Registry wiring

Use `register(registry)` when your application selects messaging adapters through a `MessagingRegistry`.

```python
from pykit_messaging import MessagingRegistry
from pykit_messaging_rabbitmq import RabbitMqConfig, register

registry = MessagingRegistry()
register(registry)

producer = registry.producer(RabbitMqConfig(url="amqp://localhost:5672/", allow_insecure_dev=True))
consumer = registry.consumer(RabbitMqConfig(topics=["events"]))
```

## What this package provides

- `RabbitMqProducer` and `RabbitMqConsumer`
- `RabbitMqConfig` for adapter-specific settings
- `register(registry)` to register the `"rabbitmq"` adapter explicitly

## Configuration highlights

- The secure default URL is `amqps://localhost:5671/`.
- Plaintext `amqp://` URLs require `allow_insecure_dev=True`.
- Credentials belong in `username` and `password`, not in the broker URL.
- `exchange_name`, `exchange_type`, `routing_key_prefix`, `queue_name`, and durability flags are configured through `RabbitMqConfig`.
- `auto_ack` must match the selected commit and delivery semantics.
- Exactly-once delivery is rejected by this adapter.

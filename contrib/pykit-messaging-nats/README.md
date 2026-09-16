# pykit-messaging-nats

Core NATS adapter package for `pykit-messaging`.

## Installation

```bash
uv add pykit-messaging-nats
# or
pip install pykit-messaging-nats
```

## Quick start

```python
from pykit_messaging_nats import NatsConfig, NatsProducer

producer = NatsProducer(
    NatsConfig(
        url="nats://localhost:4222",
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
from pykit_messaging_nats import NatsConfig, register

registry = MessagingRegistry()
register(registry)

producer = registry.producer(NatsConfig(url="nats://localhost:4222", allow_insecure_dev=True))
consumer = registry.consumer(NatsConfig(topics=["events"]))
```

## What this package provides

- `NatsProducer` and `NatsConsumer`
- `NatsConfig` for adapter-specific settings
- `register(registry)` to register the `"nats"` adapter explicitly

## Configuration highlights

- The secure default URL is `tls://localhost:4222`.
- Plaintext `nats://` URLs require `allow_insecure_dev=True`.
- Use `subject_prefix` to namespace subjects and `queue_group` for grouped consumers.
- Credentials belong in `token` or `username` and `password`, not in the server URL.
- Core NATS subjects support at-most-once delivery only. Manual acknowledgements and exactly-once delivery are rejected.

# pykit-sse

Manage Server-Sent Events clients, broadcasting, and lifecycle with bounded queues and backpressure-aware delivery.

## Installation

```bash
pip install pykit-sse
# or
uv add pykit-sse
```

## Quick start

```python
from pykit_sse import SSEClient, SSEComponent, SSEEvent, SSEHub

hub = SSEHub()
client = SSEClient("user-42", metadata={"role": "admin"})
hub.register(client)

await hub.broadcast(SSEEvent(event="update", data='{"status": "deployed"}'))
await hub.send_to("user-42", SSEEvent(event="notification", data="Hello!"))

await hub.broadcast(
    SSEEvent(event="admin-alert", data="disk full"),
    filter_fn=lambda c: c.metadata.get("role") == "admin",
)

event = await client.receive()
print(event.encode())
```

## Component lifecycle

```python
component = SSEComponent(path="/events")
await component.start()
health = await component.health()
await component.stop()
```

## What it includes

- **`SSEEvent`** models the SSE wire format and provides `encode()`.
- **`SSEClient`** wraps per-client queueing, receiving, close handling, and dropped-event tracking.
- **`SSEHub`** registers clients, broadcasts events, targets individual clients, and shuts down cleanly.
- **`SSEComponent`** adds component lifecycle and health reporting around a hub.

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)

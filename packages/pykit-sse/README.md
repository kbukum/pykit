# pykit-sse

Server-Sent Events hub for real-time client communication with async queue-based delivery and component lifecycle.

## Installation

```bash
pip install pykit-sse
# or
uv add pykit-sse
```

## Quick Start

```python
from pykit_sse import SSEHub, SSEClient, SSEEvent, SSEComponent

# Create hub and register clients
hub = SSEHub()
client = SSEClient("user-42", metadata={"role": "admin"})
hub.register(client)

# Broadcast to all clients
await hub.broadcast(SSEEvent(event="update", data='{"status": "deployed"}'))

# Send to specific client
await hub.send_to("user-42", SSEEvent(event="notification", data="Hello!"))

# Filtered broadcast
await hub.broadcast(
    SSEEvent(event="admin-alert", data="disk full"),
    filter_fn=lambda c: c.metadata.get("role") == "admin",
)

# Client receives events from its async queue
event = await client.receive()
print(event.encode())  # "event: update\ndata: {\"status\": \"deployed\"}\n\n"
```

### Component Lifecycle

```python
component = SSEComponent(path="/events")
await component.start()
health = await component.health()  # includes client count
await component.stop()  # closes all clients
```

## Key Components

- **SSEEvent** — Dataclass following SSE wire format with `event`, `data`, `id`, `retry` fields and `encode()` method
- **SSEClient** — Connected client with async queue-based event delivery (`send()`, `receive()`, `close()`)
- **SSEHub** — Central event router with `register()`, `unregister()`, `broadcast()`, `send_to()`, and `shutdown()`
- **SSEComponent** — Lifecycle-managed hub implementing Component protocol with health reporting

## Dependencies

- `pykit-errors`, `pykit-component`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

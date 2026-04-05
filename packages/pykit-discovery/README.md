# pykit-discovery

Service discovery and load balancing with pluggable providers and multiple balancing strategies.

## Installation

```bash
pip install pykit-discovery
# or
uv add pykit-discovery
```

## Quick Start

```python
import asyncio
from pykit_discovery import (
    ServiceInstance, StaticProvider, DiscoveryComponent,
    RoundRobinStrategy, LeastConnectionsStrategy,
)

# Register and discover services
provider = StaticProvider()
await provider.register(ServiceInstance(
    id="api-1", name="api", host="10.0.0.1", port=8080,
    tags=["v2"], metadata={"region": "us-east"},
))
await provider.register(ServiceInstance(
    id="api-2", name="api", host="10.0.0.2", port=8080,
))

instances = await provider.discover("api")  # returns healthy instances

# Load balancing strategies
rr = RoundRobinStrategy()
selected = rr.select(instances)  # cycles through instances

# Least-connections with connection tracking
lc = LeastConnectionsStrategy()
target = lc.select(instances)
lc.acquire(target.id)   # track in-flight connection
# ... make request ...
lc.release(target.id)   # release connection
```

## Key Components

- **ServiceInstance** — Dataclass representing a service endpoint: `id`, `name`, `host`, `port`, `protocol`, `tags`, `metadata`, `healthy`, `weight`; provides `address` (`host:port`) and `url(scheme)` helpers
- **Discovery** — Protocol: `async discover(service_name) -> list[ServiceInstance]`
- **Registry** — Protocol: `async register(instance)` and `async deregister(instance_id)`
- **StaticProvider** — In-memory provider implementing both `Discovery` and `Registry`; filters unhealthy instances
- **ConsulProvider** — Consul HTTP API integration with health checks, token auth, and datacenter support
- **LoadBalancer** — Protocol: `select(instances) -> ServiceInstance`
- **RoundRobinStrategy** — Sequential cycling through instances
- **RandomStrategy** — Random instance selection
- **LeastConnectionsStrategy** — Thread-safe strategy tracking in-flight connections with `acquire()`/`release()`; selects instance with fewest active connections
- **DiscoveryComponent** — Component lifecycle wrapper with health checks, integrates with `pykit-component`

## Dependencies

- `pykit-errors` — Error handling
- `pykit-component` — Component lifecycle protocol
- `httpx` — Async HTTP client (for Consul provider)

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

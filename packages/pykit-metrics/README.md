# pykit-metrics

Prometheus metrics helpers for gRPC services with pre-configured counters, histograms, and an HTTP metrics endpoint.

## Installation

```bash
pip install pykit-metrics
# or
uv add pykit-metrics
```

## Quick Start

```python
from pykit_metrics import MetricsCollector, start_metrics_server

# Start Prometheus metrics endpoint on port 9090
start_metrics_server(port=9090)

# Create collector for your service
collector = MetricsCollector(service_name="orders")

# Record a completed gRPC request
collector.observe_request(method="/orders.v1.Orders/Create", status="OK", duration=0.042)
```

## Key Components

- **MetricsCollector** — Collects standard gRPC metrics: request count (Counter), request duration (Histogram), and active requests (Counter), all labeled by method and status
- **start_metrics_server()** — Starts a Prometheus HTTP server in a background daemon thread (default port 9090)

## Dependencies

- `prometheus-client`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

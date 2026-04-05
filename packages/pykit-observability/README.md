# pykit-observability

OpenTelemetry tracing/metrics integration with service health monitoring and operation context management.

## Installation

```bash
pip install pykit-observability
# or
uv add pykit-observability
```

## Quick Start

```python
from pykit_observability import (
    TracerConfig, MeterConfig, setup_tracing, setup_metrics,
    ServiceHealth, HealthStatus, OperationContext,
    trace_operation, get_meter, OperationMetrics,
)

# Initialize tracing and metrics
setup_tracing(TracerConfig(service_name="orders", sample_rate=0.8))
setup_metrics(MeterConfig(service_name="orders"))

# Health monitoring
health = ServiceHealth("orders", version="1.2.0")
health.register("database")
health.register("cache")
health.update("database", HealthStatus.HEALTHY)
health.update("cache", HealthStatus.DEGRADED, "high latency")
print(health.overall_status())  # HealthStatus.DEGRADED

# Operation context with tracing
ctx = OperationContext("process_order", {"order_id": "abc-123"})
async with ctx():
    ctx.set_attribute("items", 5)
    # ... your logic here
    print(f"elapsed: {ctx.elapsed:.3f}s")
```

## Key Components

- **ServiceHealth** — Thread-safe aggregate health monitor tracking multiple components
- **ComponentHealth** — Immutable snapshot of a single component's health state
- **HealthStatus** — Enum: `HEALTHY`, `DEGRADED`, `UNHEALTHY`
- **OperationContext** — Ties request metadata, OpenTelemetry spans, and timing for an operation
- **OperationMetrics** — Pre-built counter and histogram instruments for request tracking
- **TracerConfig / MeterConfig** — Configuration dataclasses for OpenTelemetry setup
- **setup_tracing() / setup_metrics()** — Initialize global OTel tracer and meter providers
- **trace_operation()** — Async context manager that creates and manages a span
- **get_tracer() / get_meter()** — Retrieve named tracer or meter from the global provider

## Dependencies

- `pykit-errors`, `pykit-component`
- `opentelemetry-api`, `opentelemetry-sdk`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

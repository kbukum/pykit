# pykit: Integration Patterns

This document shows how pykit modules compose together to solve common microservice challenges. Each pattern demonstrates a practical workflow combining multiple packages using Python's async/await and protocol-based abstractions.

## Pattern 1: Server + Discovery

**Problem**: Start an HTTP or gRPC server and automatically register it with a discovery service (Consul, etcd, etc.) for automatic deregistration on shutdown.

**Solution**: Use `DiscoveryServer` from `pykit-discovery` to wrap your server component and handle automatic registration/deregistration via the component lifecycle.

**Code example**:

```python
import asyncio
from pykit_server import HttpServer
from pykit_discovery import DiscoveryServer, ServiceInstance
from pykit_discovery.consul import ConsulRegistry
from pykit_logging import Logger

async def setup_discovery_server(
    http_server: HttpServer,
    registry,
    log: Logger,
) -> DiscoveryServer:
    """Wrap HTTP server with discovery integration."""
    instance = ServiceInstance(
        id="payment-svc-1",
        name="payment-service",
        address="127.0.0.1",
        port=8080,
        tags=["v1", "prod"],
        metadata={"region": "us-west"},
    )
    
    discovery_server = DiscoveryServer(http_server, registry, instance)
    return discovery_server

async def main():
    log = Logger()
    
    # Create HTTP server
    http_server = HttpServer(host="0.0.0.0", port=8080)
    
    # Setup discovery registry (e.g., Consul)
    registry = ConsulRegistry(host="localhost", port=8500)
    
    # Wrap with discovery
    disc_server = await setup_discovery_server(http_server, registry, log)
    
    # Start (auto-registers on start, deregisters on stop)
    await disc_server.start()
    
    try:
        # Keep running
        await asyncio.sleep(float('inf'))
    finally:
        await disc_server.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

**Modules involved**:
- `pykit-server` — `HttpServer`, `GrpcServer`
- `pykit-discovery` — `DiscoveryServer`, `ServiceInstance`, `Registry`
- `pykit-logging` — `Logger`

---

## Pattern 2: Messaging + Middleware Stack

**Problem**: Process messages from a topic with automatic retry, metrics tracking, deduplication, and circuit breaker protection without manually nesting middleware.

**Solution**: Use `StackBuilder` from `pykit-messaging` to compose a typed middleware stack with a fluent API. The builder applies middleware in a fixed, sensible order.

**Code example**:

```python
import asyncio
from pykit_messaging import EventPublisher, MessageHandlerProtocol
from pykit_messaging.middleware import StackBuilder, RetryConfig, DedupConfig, CircuitBreakerConfig
from pykit_messaging.kafka import KafkaConsumer
from pykit_metrics import MetricsCollector
from pykit_logging import Logger

class OrderHandler(MessageHandlerProtocol):
    """Custom handler for order events."""
    
    def __init__(self, log: Logger):
        self.log = log
    
    async def handle(self, msg: dict) -> None:
        """Process order message."""
        self.log.info(f"Processing order: {msg}")
        # Your business logic here

async def setup_message_handler(log: Logger) -> MessageHandlerProtocol:
    """Build a resilient message handler with middleware stack."""
    # Create base handler
    base_handler = OrderHandler(log)
    
    # Create metrics collector
    metrics = MetricsCollector()
    
    # Build resilient handler with middleware
    handler = (
        StackBuilder(base_handler)
        .with_retry(RetryConfig(
            max_attempts=3,
            backoff_ms=100,
            dlq_topic="orders.dlq",
        ))
        .with_metrics(metrics, "orders.created")
        .with_dedup(DedupConfig(window_seconds=60))
        .with_circuit_breaker(CircuitBreakerConfig(
            failure_threshold=5,
            success_threshold=2,
            timeout_seconds=30,
        ))
        .build()
    )
    
    return handler

async def main():
    log = Logger()
    
    # Setup message handler with middleware
    handler = await setup_message_handler(log)
    
    # Create Kafka consumer with wrapped handler
    consumer = KafkaConsumer(
        brokers=["localhost:9092"],
        topic="orders.created",
        group_id="order-processor",
        handler=handler,
    )
    
    # Run consumer
    await consumer.start()
    
    try:
        # Keep running
        await asyncio.sleep(float('inf'))
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(main())
```

**Modules involved**:
- `pykit-messaging` — `StackBuilder`, `MessageHandlerProtocol`, middleware config classes
- `pykit-messaging.kafka` — `KafkaConsumer`
- `pykit-metrics` — `MetricsCollector`
- `pykit-logging` — `Logger`

---

## Pattern 3: gRPC Client + Discovery

**Problem**: Create a gRPC client that dynamically discovers and connects to a remote service with automatic load balancing and connection pooling.

**Solution**: Use `DiscoveryChannel` from `pykit-grpc` to wrap gRPC channels with service discovery. The channel automatically resolves service names and handles load balancing.

**Code example**:

```python
import asyncio
from pykit_grpc import DiscoveryChannel, GrpcConfig
from pykit_discovery import ConsulDiscovery, Strategy
from pykit_logging import Logger

# Generated gRPC stub (from protobuf)
# from analysis_pb2_grpc import AnalysisServiceStub

async def setup_analysis_client(log: Logger):
    """Create a discovery-based gRPC client."""
    # Create discovery client
    discovery = ConsulDiscovery(host="localhost", port=8500)
    
    # Create gRPC channel with discovery
    channel = DiscoveryChannel(
        service_name="analysis-service",
        discovery=discovery,
        strategy=Strategy.ROUND_ROBIN,
        log=log,
    )
    
    # Create typed gRPC client from channel
    # client = AnalysisServiceStub(channel)
    # return client
    return channel

async def main():
    log = Logger()
    
    # Setup gRPC client with discovery
    channel = await setup_analysis_client(log)
    
    # First call triggers service discovery and connection
    # response = await client.analyze(AnalyzeRequest(data="hello world"))
    # print(f"Analysis result: {response}")

if __name__ == "__main__":
    asyncio.run(main())
```

**Modules involved**:
- `pykit-grpc` — `DiscoveryChannel`, `GrpcConfig`
- `pykit-discovery` — `Discovery`, `ConsulDiscovery`, `Strategy`
- `pykit-logging` — `Logger`

---

## Pattern 4: Observability + OTLP

**Problem**: Export metrics and traces to an observability platform (Grafana, Jaeger, etc.) for comprehensive monitoring.

**Solution**: Use `setup_otlp_tracing()` and `setup_otlp_metrics()` from `pykit-observability` to configure trace and metric exporters with minimal code.

**Code example**:

```python
import asyncio
from pykit_observability import setup_otlp_tracing, setup_otlp_metrics, TracerProvider, MeterProvider
from pykit_logging import Logger

async def setup_observability(service_name: str, log: Logger) -> tuple[TracerProvider, MeterProvider]:
    """Configure OTLP tracing and metrics export."""
    
    # Setup tracing exporter
    tracer_provider = await setup_otlp_tracing(
        service_name=service_name,
        otlp_endpoint="http://localhost:4317",
        log=log,
    )
    
    # Setup metrics exporter
    meter_provider = await setup_otlp_metrics(
        service_name=service_name,
        otlp_endpoint="http://localhost:4317",
        log=log,
    )
    
    return tracer_provider, meter_provider

async def main():
    log = Logger()
    
    # Setup observability
    tracer_provider, meter_provider = await setup_observability("order-service", log)
    
    # Get tracer and meter for use in application
    tracer = tracer_provider.get_tracer(__name__)
    meter = meter_provider.get_meter(__name__)
    
    # Create metrics and spans in your handlers
    counter = meter.create_counter("orders.processed", description="Total orders processed")
    
    async with tracer.start_as_current_span("process_order") as span:
        counter.add(1)
        # Process order...
        log.info("Order processed successfully")

if __name__ == "__main__":
    asyncio.run(main())
```

**Modules involved**:
- `pykit-observability` — `setup_otlp_tracing()`, `setup_otlp_metrics()`
- `pykit-logging` — `Logger`

---

## Pattern 5: EventPublisher + Messaging

**Problem**: Publish domain events with automatic envelope construction (UUID, timestamp, source) without manual envelope handling.

**Solution**: Use `EventPublisher` from `pykit-messaging` to wrap a Kafka producer. The facade handles Event envelope creation automatically.

**Code example**:

```python
import asyncio
from dataclasses import dataclass
from pykit_messaging import EventPublisher
from pykit_messaging.kafka import KafkaProducer
from pykit_logging import Logger

@dataclass
class OrderCreatedEvent:
    order_id: str
    customer_id: str
    amount: float

async def publish_order_events() -> EventPublisher:
    """Create an event publisher for order events."""
    # Create Kafka producer
    producer = KafkaProducer(brokers=["localhost:9092"])
    await producer.start()
    
    # Wrap with EventPublisher for auto-envelope
    event_pub = EventPublisher(producer, source="order-service")
    return event_pub

async def main():
    log = Logger()
    
    # Create event publisher
    event_pub = await publish_order_events()
    
    # Publish event (no manual envelope needed)
    order_event = OrderCreatedEvent(
        order_id="order-123",
        customer_id="cust-456",
        amount=99.99,
    )
    
    await event_pub.publish(
        topic="orders.created",
        event_type="order.created.v1",
        data=order_event,
    )
    
    # Publish with partition key for ordering
    await event_pub.publish_keyed(
        topic="orders.created",
        event_type="order.created.v1",
        data=order_event,
        key="cust-456",  # ensures all events for this customer go to same partition
    )
    
    # Publish batch of events
    orders = [
        OrderCreatedEvent("order-124", "cust-457", 199.99),
        OrderCreatedEvent("order-125", "cust-458", 149.99),
    ]
    await event_pub.publish_batch(
        topic="orders.created",
        event_type="order.created.v1",
        items=orders,
    )

if __name__ == "__main__":
    asyncio.run(main())
```

**Modules involved**:
- `pykit-messaging` — `EventPublisher`, `Event`
- `pykit-messaging.kafka` — `KafkaProducer`
- `pykit-logging` — `Logger`

---

## Pattern 6: TickerWorker + Component

**Problem**: Run periodic health checks or background tasks reliably within a component lifecycle.

**Solution**: Use `TickerWorker` from `pykit-worker` to wrap async functions as periodic background tasks that integrate with the component lifecycle.

**Code example**:

```python
import asyncio
from pykit_worker import TickerWorker
from pykit_component import ComponentRegistry, Health, HealthStatus
from pykit_logging import Logger

class HealthCheckService:
    """Service with cache health checks."""
    
    def __init__(self, log: Logger):
        self.log = log
        self.cache_healthy = True
    
    async def check_cache_health(self) -> None:
        """Periodic health check for cache."""
        try:
            # Simulate cache health check
            result = await self._ping_cache()
            self.cache_healthy = True
            self.log.debug("Cache is healthy")
        except Exception as e:
            self.cache_healthy = False
            self.log.warn(f"Cache health check failed: {e}")
    
    async def _ping_cache(self) -> bool:
        """Ping cache backend."""
        # Your cache ping logic here
        return True
    
    def should_use_cache_optimization(self) -> bool:
        """Feature flag based on cache health."""
        return self.cache_healthy

async def setup_health_checker(log: Logger) -> TickerWorker:
    """Create a periodic health checker."""
    health_svc = HealthCheckService(log)
    
    # Create a ticker that runs cache health check every 30 seconds
    ticker = TickerWorker(
        name="cache-health-check",
        interval=30.0,
        handler=health_svc.check_cache_health,
    )
    
    return ticker

async def main():
    log = Logger()
    registry = ComponentRegistry()
    
    # Setup health checker
    health_ticker = await setup_health_checker(log)
    registry.register(health_ticker)
    
    # Start all components
    await registry.start_all()
    
    try:
        # Keep running
        await asyncio.sleep(float('inf'))
    finally:
        await registry.stop_all()

if __name__ == "__main__":
    asyncio.run(main())
```

**Modules involved**:
- `pykit-worker` — `TickerWorker`
- `pykit-component` — `ComponentRegistry`, `Health`, `HealthStatus`
- `pykit-logging` — `Logger`

---

## Cross-Pattern Composition

All six patterns work together in a complete microservice:

1. **Service Registration** (Pattern 1) makes your service discoverable.
2. **gRPC Clients** (Pattern 3) use discovery to call downstream services.
3. **Message Processing** (Pattern 2) uses middleware stacks to handle async events reliably.
4. **Event Publishing** (Pattern 5) broadcasts domain events to consumers.
5. **Observability** (Pattern 4) exports metrics and traces for monitoring.
6. **Periodic Tasks** (Pattern 6) run background maintenance tasks.

**Example architecture**:

```python
# main.py — complete microservice wiring
import asyncio
from pykit_server import HttpServer
from pykit_discovery import DiscoveryServer, ServiceInstance, ConsulRegistry
from pykit_messaging import EventPublisher, StackBuilder
from pykit_messaging.kafka import KafkaProducer, KafkaConsumer
from pykit_grpc import DiscoveryChannel
from pykit_observability import setup_otlp_tracing, setup_otlp_metrics
from pykit_worker import TickerWorker
from pykit_component import ComponentRegistry
from pykit_logging import Logger

async def main():
    log = Logger()
    registry = ComponentRegistry()
    
    # 1. HTTP server with discovery
    http_server = HttpServer(host="0.0.0.0", port=8080)
    consul_registry = ConsulRegistry(host="localhost", port=8500)
    instance = ServiceInstance(
        id="order-svc-1",
        name="order-service",
        address="127.0.0.1",
        port=8080,
        tags=["v1"],
    )
    disc_server = DiscoveryServer(http_server, consul_registry, instance)
    registry.register(disc_server)
    
    # 2. Kafka producer and event publisher
    kafka_producer = KafkaProducer(brokers=["localhost:9092"])
    event_pub = EventPublisher(kafka_producer, source="order-service")
    
    # 3. Message handler with middleware stack
    class OrderHandler:
        async def handle(self, msg: dict) -> None:
            log.info(f"Processing order: {msg}")
    
    base_handler = OrderHandler()
    handler = (
        StackBuilder(base_handler)
        .with_retry()
        .with_metrics(MetricsCollector(), "orders.created")
        .build()
    )
    consumer = KafkaConsumer(
        brokers=["localhost:9092"],
        topic="orders.created",
        group_id="order-processor",
        handler=handler,
    )
    registry.register(consumer)
    
    # 4. gRPC client with discovery
    discovery = ConsulDiscovery(host="localhost", port=8500)
    grpc_channel = DiscoveryChannel("analysis-service", discovery, log=log)
    
    # 5. Observability setup
    tracer_provider, meter_provider = await setup_otlp_tracing(
        service_name="order-service",
        otlp_endpoint="http://localhost:4317",
    ), await setup_otlp_metrics(
        service_name="order-service",
        otlp_endpoint="http://localhost:4317",
    )
    
    # 6. Periodic health check
    class HealthCheck:
        async def check(self) -> None:
            log.info("Health check running")
    
    health_ticker = TickerWorker("health-check", interval=30.0, handler=HealthCheck().check)
    registry.register(health_ticker)
    
    # Start all components
    await registry.start_all()
    
    try:
        await asyncio.sleep(float('inf'))
    finally:
        await registry.stop_all()

if __name__ == "__main__":
    asyncio.run(main())
```

This architecture provides:
- ✅ **Discoverability** — other services find and call you
- ✅ **Resilience** — retries, circuit breakers for message processing
- ✅ **Observability** — metrics and traces exported to OTLP platform
- ✅ **Event-driven communication** — publish and consume async events
- ✅ **Graceful degradation** — background tasks track system health
- ✅ **Protocol-based abstractions** — easy to mock and test

---

## Best Practices

1. **Use DiscoveryServer** for service registration to ensure automatic deregistration on shutdown.
2. **Compose middleware with StackBuilder** rather than manually nesting; it ensures predictable order (metrics → dedup → circuit breaker → retry).
3. **Use DiscoveryChannel for gRPC** to enable dynamic service discovery without hardcoding addresses.
4. **Publish events with EventPublisher** to ensure consistent Event envelopes across your system.
5. **Setup OTLP observability early** to get metrics and traces from the start.
6. **Use TickerWorker for periodic tasks** to integrate with component lifecycle and get health reporting automatically.
7. **Leverage ComponentRegistry** to manage component startup order and ensure graceful shutdown.

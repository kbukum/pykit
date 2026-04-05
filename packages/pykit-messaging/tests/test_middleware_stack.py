"""Tests for middleware stack builder and new middleware."""

from __future__ import annotations

import pytest

from pykit_messaging.handler import FuncHandler, MessageHandlerProtocol
from pykit_messaging.middleware.retry import RetryConfig, RetryHandler, retry
from pykit_messaging.middleware.metrics import MetricsHandler, instrument
from pykit_messaging.middleware.dead_letter import DeadLetterConfig, DeadLetterProducer
from pykit_messaging.middleware.stack import StackBuilder
from pykit_messaging.types import Message


def _make_msg(key: str = "k", topic: str = "t") -> Message:
    """Create a test message."""
    return Message(key=key, value=b"v", topic=topic, partition=0, offset=0)


class CountingCollector:
    """Metrics collector that counts calls."""

    def __init__(self) -> None:
        self.consumes: list[tuple[str, float, bool]] = []

    def record_publish(self, topic: str, duration_ms: float, *, success: bool) -> None:
        """Record publish (no-op for tests)."""

    def record_consume(self, topic: str, duration_ms: float, *, success: bool) -> None:
        """Record consume metric."""
        self.consumes.append((topic, duration_ms, success))


class MockProducer:
    """Mock message producer for testing."""

    def __init__(self) -> None:
        self.sent: list[tuple[str, bytes]] = []

    async def send(
        self,
        topic: str,
        value: bytes,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send a message."""
        self.sent.append((topic, value))

    async def send_event(self, topic: str, event) -> None:
        """Send an event (no-op)."""

    async def send_json(self, topic: str, data, key: str | None = None) -> None:
        """Send JSON (no-op)."""

    async def send_batch(self, messages: list[Message]) -> None:
        """Send batch (no-op)."""

    async def flush(self) -> None:
        """Flush (no-op)."""

    async def close(self) -> None:
        """Close (no-op)."""


@pytest.mark.asyncio
async def test_retry_succeeds_after_failures() -> None:
    """Test that retry successfully recovers from transient failures."""
    attempts = 0

    async def handler(msg: Message) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("fail")

    wrapped = RetryHandler(FuncHandler(handler), RetryConfig(max_attempts=3, initial_backoff=0.001))
    await wrapped.handle(_make_msg())
    assert attempts == 3


@pytest.mark.asyncio
async def test_retry_exhausted_calls_callback() -> None:
    """Test that exhaustion callback is called when retries are exhausted."""
    exhausted_msgs: list[Message] = []

    async def on_exhausted(msg: Message, err: Exception) -> None:
        exhausted_msgs.append(msg)

    async def always_fail(msg: Message) -> None:
        raise RuntimeError("boom")

    cfg = RetryConfig(max_attempts=2, initial_backoff=0.001, on_exhausted=on_exhausted)
    wrapped = RetryHandler(FuncHandler(always_fail), cfg)

    with pytest.raises(RuntimeError, match="boom"):
        await wrapped.handle(_make_msg())

    assert len(exhausted_msgs) == 1


@pytest.mark.asyncio
async def test_metrics_records_success() -> None:
    """Test that metrics are recorded on successful message handling."""
    collector = CountingCollector()

    async def noop(msg: Message) -> None:
        pass

    wrapped = MetricsHandler(FuncHandler(noop), collector, "test-topic")
    await wrapped.handle(_make_msg())

    assert len(collector.consumes) == 1
    topic, duration_ms, success = collector.consumes[0]
    assert topic == "test-topic"
    assert success is True
    assert duration_ms >= 0


@pytest.mark.asyncio
async def test_metrics_records_failure() -> None:
    """Test that metrics are recorded on message handling failure."""
    collector = CountingCollector()

    async def fail(msg: Message) -> None:
        raise RuntimeError("fail")

    wrapped = MetricsHandler(FuncHandler(fail), collector, "t")

    with pytest.raises(RuntimeError):
        await wrapped.handle(_make_msg())

    assert len(collector.consumes) == 1
    assert collector.consumes[0][2] is False


@pytest.mark.asyncio
async def test_dead_letter_sends_to_dlq() -> None:
    """Test that failed messages are sent to dead-letter topic."""
    producer = MockProducer()
    dlq = DeadLetterProducer(producer)

    msg = _make_msg(topic="orders")
    await dlq.send(msg, RuntimeError("bad"))

    assert len(producer.sent) == 1
    assert producer.sent[0][0] == "orders.dlq"


@pytest.mark.asyncio
async def test_dead_letter_custom_suffix() -> None:
    """Test that custom DLQ suffix is applied."""
    producer = MockProducer()
    dlq = DeadLetterProducer(producer, DeadLetterConfig(suffix="-error"))

    msg = _make_msg(topic="orders")
    await dlq.send(msg, RuntimeError("bad"))

    assert len(producer.sent) == 1
    assert producer.sent[0][0] == "orders-error"


@pytest.mark.asyncio
async def test_stack_builder_no_middleware() -> None:
    """Test builder with no middleware applied."""
    called = False

    async def handler(msg: Message) -> None:
        nonlocal called
        called = True

    wrapped = StackBuilder(FuncHandler(handler)).build()
    await wrapped.handle(_make_msg())
    assert called


@pytest.mark.asyncio
async def test_stack_builder_with_metrics_and_retry() -> None:
    """Test builder with metrics and retry middleware."""
    attempts = 0
    collector = CountingCollector()

    async def handler(msg: Message) -> None:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("fail")

    wrapped = (
        StackBuilder(FuncHandler(handler))
        .with_retry(RetryConfig(max_attempts=3, initial_backoff=0.001))
        .with_metrics(collector, "my-topic")
        .build()
    )

    await wrapped.handle(_make_msg())
    assert attempts == 2
    # Metrics should record the overall result (success after retries)
    assert len(collector.consumes) == 1
    assert collector.consumes[0][2] is True


@pytest.mark.asyncio
async def test_stack_builder_fluent_api() -> None:
    """Test that StackBuilder fluent API returns self."""
    base_handler = FuncHandler(lambda msg: None)
    builder = StackBuilder(base_handler)

    result1 = builder.with_retry()
    result2 = result1.with_metrics(CountingCollector(), "topic")

    # Should be able to chain all methods
    assert result1 is builder
    assert result2 is builder

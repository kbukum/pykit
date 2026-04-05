"""Tests for ManagedProducer lifecycle and metrics."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from pykit_messaging.managed_producer import ManagedProducer
from pykit_messaging.memory import InMemoryBroker
from pykit_messaging.metrics import MetricsCollector, NoopMetrics
from pykit_messaging.types import Event, Message


@dataclass
class FakeMetrics:
    """Test metrics collector that records calls."""

    publishes: list[tuple[str, float, bool]] = field(default_factory=list)
    consumes: list[tuple[str, float, bool]] = field(default_factory=list)

    def record_publish(self, topic: str, duration_ms: float, *, success: bool) -> None:
        self.publishes.append((topic, duration_ms, success))

    def record_consume(self, topic: str, duration_ms: float, *, success: bool) -> None:
        self.consumes.append((topic, duration_ms, success))


class TestManagedProducerLifecycle:
    async def test_start_and_stop(self) -> None:
        broker = InMemoryBroker()
        mp = ManagedProducer(broker.producer(), "test-producer")

        assert not mp.is_running
        await mp.start()
        assert mp.is_running
        await mp.stop()
        assert not mp.is_running

    async def test_start_twice_raises(self) -> None:
        broker = InMemoryBroker()
        mp = ManagedProducer(broker.producer(), "test-producer")
        await mp.start()

        with pytest.raises(RuntimeError, match="already running"):
            await mp.start()

        await mp.stop()

    async def test_stop_when_not_running_is_noop(self) -> None:
        broker = InMemoryBroker()
        mp = ManagedProducer(broker.producer(), "test-producer")
        await mp.stop()  # should not raise

    async def test_send_before_start_raises(self) -> None:
        broker = InMemoryBroker()
        mp = ManagedProducer(broker.producer(), "test-producer")

        with pytest.raises(RuntimeError, match="not running"):
            await mp.send("t", b"data")

    async def test_close_stops_producer(self) -> None:
        broker = InMemoryBroker()
        mp = ManagedProducer(broker.producer(), "test-producer")
        await mp.start()
        await mp.close()
        assert not mp.is_running


class TestManagedProducerDelegation:
    async def test_send_delegates(self) -> None:
        broker = InMemoryBroker()
        consumer = broker.consumer(topics=["t1"])
        mp = ManagedProducer(broker.producer(), "test-producer")
        await mp.start()

        await mp.send("t1", b"hello", key="k1", headers={"h": "v"})
        await mp.stop()

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)
            await consumer.close()

        await consumer.consume(handler)
        assert len(received) == 1
        assert received[0].value == b"hello"
        assert received[0].key == "k1"

    async def test_send_event_delegates(self) -> None:
        broker = InMemoryBroker()
        consumer = broker.consumer(topics=["events"])
        mp = ManagedProducer(broker.producer(), "test-producer")
        await mp.start()

        evt = Event(type="test.event", source="test", subject="s1", data={"a": 1})
        await mp.send_event("events", evt)
        await mp.stop()

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)
            await consumer.close()

        await consumer.consume(handler)
        assert len(received) == 1
        parsed = Event.from_json(received[0].value)
        assert parsed.type == "test.event"

    async def test_send_json_delegates(self) -> None:
        broker = InMemoryBroker()
        consumer = broker.consumer(topics=["json"])
        mp = ManagedProducer(broker.producer(), "test-producer")
        await mp.start()

        await mp.send_json("json", {"key": "value"})
        await mp.stop()

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)
            await consumer.close()

        await consumer.consume(handler)
        assert len(received) == 1

    async def test_send_batch_delegates(self) -> None:
        broker = InMemoryBroker()
        consumer = broker.consumer(topics=["batch"])
        mp = ManagedProducer(broker.producer(), "test-producer")
        await mp.start()

        msgs = [
            Message(key="k1", value=b"a", topic="batch", partition=0, offset=0),
            Message(key="k2", value=b"b", topic="batch", partition=0, offset=1),
        ]
        await mp.send_batch(msgs)
        await mp.stop()

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)
            if len(received) >= 2:
                await consumer.close()

        await consumer.consume(handler)
        assert len(received) == 2

    async def test_flush_delegates(self) -> None:
        broker = InMemoryBroker()
        mp = ManagedProducer(broker.producer(), "test-producer")
        await mp.start()
        await mp.flush()  # should not raise
        await mp.stop()


class TestManagedProducerMetrics:
    async def test_metrics_recorded_on_send(self) -> None:
        broker = InMemoryBroker()
        metrics = FakeMetrics()
        mp = ManagedProducer(broker.producer(), "test-producer", metrics=metrics)
        await mp.start()

        await mp.send("t1", b"data")
        await mp.stop()

        assert len(metrics.publishes) == 1
        topic, duration_ms, success = metrics.publishes[0]
        assert topic == "t1"
        assert duration_ms >= 0
        assert success is True

    async def test_metrics_recorded_on_send_event(self) -> None:
        broker = InMemoryBroker()
        metrics = FakeMetrics()
        mp = ManagedProducer(broker.producer(), "test-producer", metrics=metrics)
        await mp.start()

        evt = Event(type="test", source="s")
        await mp.send_event("events", evt)
        await mp.stop()

        assert len(metrics.publishes) == 1
        assert metrics.publishes[0][0] == "events"
        assert metrics.publishes[0][2] is True

    async def test_noop_metrics_does_not_error(self) -> None:
        broker = InMemoryBroker()
        mp = ManagedProducer(broker.producer(), "test-producer")
        await mp.start()
        await mp.send("t", b"data")
        await mp.stop()

    async def test_fake_metrics_satisfies_protocol(self) -> None:
        assert isinstance(FakeMetrics(), MetricsCollector)
        assert isinstance(NoopMetrics(), MetricsCollector)

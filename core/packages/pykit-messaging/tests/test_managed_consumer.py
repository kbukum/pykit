"""Tests for ManagedConsumer lifecycle and consumption."""

from __future__ import annotations

import asyncio

import pytest

from pykit_messaging.handler import FuncHandler
from pykit_messaging.managed_consumer import ManagedConsumer
from pykit_messaging.memory import InMemoryBroker
from pykit_messaging.types import Message


class TestManagedConsumerLifecycle:
    async def test_start_and_stop(self) -> None:
        broker = InMemoryBroker()
        consumer = broker.consumer(topics=["t1"])

        async def noop(msg: Message) -> None:
            pass

        mc = ManagedConsumer(consumer, FuncHandler(noop), "test-consumer")

        assert not mc.is_running
        await mc.start()
        assert mc.is_running
        await mc.stop()
        assert not mc.is_running

    async def test_start_twice_raises(self) -> None:
        broker = InMemoryBroker()
        consumer = broker.consumer(topics=["t1"])

        async def noop(msg: Message) -> None:
            pass

        mc = ManagedConsumer(consumer, FuncHandler(noop), "test-consumer")
        await mc.start()

        with pytest.raises(RuntimeError, match="already running"):
            await mc.start()

        await mc.stop()

    async def test_stop_when_not_running_is_noop(self) -> None:
        broker = InMemoryBroker()
        consumer = broker.consumer(topics=["t1"])

        async def noop(msg: Message) -> None:
            pass

        mc = ManagedConsumer(consumer, FuncHandler(noop), "test-consumer")
        await mc.stop()  # should not raise


class TestManagedConsumerConsumption:
    async def test_consumes_messages(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["t1"])

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        mc = ManagedConsumer(consumer, FuncHandler(handler), "test-consumer")
        await mc.start()

        await producer.send("t1", b"hello")
        # Give the consumption loop time to process
        await asyncio.sleep(0.1)

        await mc.stop()
        assert len(received) == 1
        assert received[0].value == b"hello"

    async def test_consumes_multiple_messages(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["t1"])

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        mc = ManagedConsumer(consumer, FuncHandler(handler), "test-consumer")
        await mc.start()

        for i in range(5):
            await producer.send("t1", f"msg-{i}".encode())

        await asyncio.sleep(0.2)
        await mc.stop()

        assert len(received) == 5

    async def test_metrics_recorded_on_consume(self) -> None:
        from dataclasses import dataclass, field

        @dataclass
        class FakeMetrics:
            publishes: list[tuple[str, float, bool]] = field(default_factory=list)
            consumes: list[tuple[str, float, bool]] = field(default_factory=list)

            def record_publish(self, topic: str, duration_ms: float, *, success: bool) -> None:
                self.publishes.append((topic, duration_ms, success))

            def record_consume(self, topic: str, duration_ms: float, *, success: bool) -> None:
                self.consumes.append((topic, duration_ms, success))

        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["t1"])
        metrics = FakeMetrics()

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        mc = ManagedConsumer(consumer, FuncHandler(handler), "test-consumer", metrics=metrics)
        await mc.start()

        await producer.send("t1", b"data")
        await asyncio.sleep(0.1)
        await mc.stop()

        assert len(metrics.consumes) == 1
        topic, duration_ms, success = metrics.consumes[0]
        assert topic == "t1"
        assert duration_ms >= 0
        assert success is True

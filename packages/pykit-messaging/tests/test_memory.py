"""Tests for InMemoryBroker."""

from __future__ import annotations

import json

from pykit_messaging.memory import InMemoryBroker
from pykit_messaging.types import Event, Message


class TestInMemoryBroker:
    def test_producer_and_consumer_creation(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["t1"])
        assert producer is not None
        assert consumer is not None

    async def test_send_and_receive(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["test"])

        await producer.send("test", b"hello", key="k1")

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)
            await consumer.close()

        await consumer.consume(handler)

        assert len(received) == 1
        assert received[0].value == b"hello"
        assert received[0].key == "k1"
        assert received[0].topic == "test"

    async def test_send_event(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["events"])

        evt = Event(type="user.created", source="test-svc", subject="user-1", data={"name": "Alice"})
        await producer.send_event("events", evt)

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)
            await consumer.close()

        await consumer.consume(handler)

        assert len(received) == 1
        parsed = Event.from_json(received[0].value)
        assert parsed.type == "user.created"
        assert parsed.data == {"name": "Alice"}

    async def test_send_json(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["json-topic"])

        await producer.send_json("json-topic", {"foo": "bar"}, key="k1")

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)
            await consumer.close()

        await consumer.consume(handler)

        assert len(received) == 1
        assert json.loads(received[0].value) == {"foo": "bar"}

    async def test_send_batch(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["batch"])

        msgs = [
            Message(key="k1", value=b"a", topic="batch", partition=0, offset=0),
            Message(key="k2", value=b"b", topic="batch", partition=0, offset=1),
        ]
        await producer.send_batch(msgs)

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)
            if len(received) >= 2:
                await consumer.close()

        await consumer.consume(handler)

        assert len(received) == 2
        assert received[0].value == b"a"
        assert received[1].value == b"b"

    async def test_subscribe(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=[])

        await producer.send("t1", b"msg1")
        await consumer.subscribe(["t1"])

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)
            await consumer.close()

        await consumer.consume(handler)
        assert len(received) == 1

    async def test_flush_and_close_are_noops(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        await producer.flush()
        await producer.close()

    async def test_consumer_close(self) -> None:
        broker = InMemoryBroker()
        consumer = broker.consumer(topics=["t1"])
        await consumer.close()

    async def test_multiple_topics(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["t1", "t2"])

        await producer.send("t1", b"from-t1")
        await producer.send("t2", b"from-t2")

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)
            if len(received) >= 2:
                await consumer.close()

        await consumer.consume(handler)

        assert len(received) == 2
        topics = {m.topic for m in received}
        assert topics == {"t1", "t2"}

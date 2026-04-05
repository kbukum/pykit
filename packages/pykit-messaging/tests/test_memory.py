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


class TestInMemoryBrokerHistory:
    """Tests for message history, topic helpers, and test assertions."""

    async def test_messages_returns_topic_history(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()

        await producer.send("t1", b"a", key="k1")
        await producer.send("t1", b"b", key="k2")
        await producer.send("t2", b"c", key="k3")

        msgs = broker.messages("t1")
        assert len(msgs) == 2
        assert msgs[0].value == b"a"
        assert msgs[1].value == b"b"

    async def test_all_messages(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()

        await producer.send("t1", b"a")
        await producer.send("t2", b"b")
        await producer.send("t1", b"c")

        assert len(broker.all_messages()) == 3

    async def test_message_count(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()

        assert broker.message_count("t1") == 0
        await producer.send("t1", b"x")
        assert broker.message_count("t1") == 1

    async def test_reset(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()

        await producer.send("t1", b"x")
        broker.reset()
        assert broker.message_count("t1") == 0

    def test_create_topic(self) -> None:
        broker = InMemoryBroker()
        broker.create_topic("new-topic")
        assert "new-topic" in broker.topics()

    async def test_topics_sorted(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()

        broker.create_topic("z-topic")
        broker.create_topic("a-topic")
        await producer.send("m-topic", b"x")

        assert broker.topics() == ["a-topic", "m-topic", "z-topic"]

    async def test_send_batch_records_history(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()

        msgs = [
            Message(key="k1", value=b"a", topic="batch", partition=0, offset=0),
            Message(key="k2", value=b"b", topic="batch", partition=0, offset=1),
        ]
        await producer.send_batch(msgs)

        assert broker.message_count("batch") == 2


class TestAssertionHelpers:
    """Tests for the testing.py assertion helpers."""

    async def test_assert_published(self) -> None:
        from pykit_messaging.testing import assert_published

        broker = InMemoryBroker()
        producer = broker.producer()

        await producer.send("t1", b"hello")
        await producer.send("t1", b"world")

        assert_published(broker, "t1", lambda m: m.value == b"world")

    async def test_assert_published_n(self) -> None:
        from pykit_messaging.testing import assert_published_n

        broker = InMemoryBroker()
        producer = broker.producer()

        await producer.send("t1", b"a")
        await producer.send("t1", b"b")

        assert_published_n(broker, "t1", 2)

    async def test_assert_no_messages(self) -> None:
        from pykit_messaging.testing import assert_no_messages

        broker = InMemoryBroker()
        assert_no_messages(broker, "empty-topic")

    async def test_wait_for_message(self) -> None:
        import asyncio

        from pykit_messaging.testing import wait_for_message

        broker = InMemoryBroker()
        producer = broker.producer()

        async def publish_later() -> None:
            await asyncio.sleep(0.02)
            await producer.send("t1", b"delayed")

        task = asyncio.create_task(publish_later())
        msg = await wait_for_message(broker, "t1", timeout=2.0)
        assert msg.value == b"delayed"
        await task

    async def test_wait_for_message_timeout(self) -> None:
        import pytest

        from pykit_messaging.testing import wait_for_message

        broker = InMemoryBroker()
        with pytest.raises(TimeoutError):
            await wait_for_message(broker, "empty", timeout=0.05)

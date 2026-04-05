"""Tests for provider bridge adapters."""

from __future__ import annotations

import asyncio

from pykit_messaging.bridge.provider import ConsumerStream, ProducerSink
from pykit_messaging.memory import InMemoryBroker
from pykit_messaging.types import Message


class TestProducerSink:
    async def test_name_property(self) -> None:
        broker = InMemoryBroker()
        sink = ProducerSink("my-sink", broker.producer(), "topic-a")
        assert sink.name == "my-sink"

    async def test_is_available(self) -> None:
        broker = InMemoryBroker()
        sink = ProducerSink("sink", broker.producer(), "topic-a")
        assert await sink.is_available() is True

    async def test_send_publishes_to_topic(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["out"])
        sink = ProducerSink("sink", producer, "out")

        msg = Message(key="k1", value=b"hello", topic="ignored", partition=0, offset=0)
        await sink.send(msg)

        received: list[Message] = []

        async def handler(m: Message) -> None:
            received.append(m)
            await consumer.close()

        await consumer.consume(handler)

        assert len(received) == 1
        assert received[0].value == b"hello"
        assert received[0].key == "k1"
        assert received[0].topic == "out"

    async def test_send_preserves_headers(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["out"])
        sink = ProducerSink("sink", producer, "out")

        msg = Message(
            key="k1",
            value=b"data",
            topic="ignored",
            partition=0,
            offset=0,
            headers={"x-trace": "abc"},
        )
        await sink.send(msg)

        received: list[Message] = []

        async def handler(m: Message) -> None:
            received.append(m)
            await consumer.close()

        await consumer.consume(handler)

        assert received[0].headers == {"x-trace": "abc"}


class TestConsumerStream:
    async def test_name_property(self) -> None:
        broker = InMemoryBroker()
        stream = ConsumerStream("my-stream", broker.consumer(topics=["t"]))
        assert stream.name == "my-stream"

    async def test_is_available(self) -> None:
        broker = InMemoryBroker()
        stream = ConsumerStream("stream", broker.consumer(topics=["t"]))
        assert await stream.is_available() is True

    async def test_execute_streams_messages(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["events"])
        stream = ConsumerStream("stream", consumer)

        await producer.send("events", b"msg1", key="k1")
        await producer.send("events", b"msg2", key="k2")

        it = await stream.execute(None)

        msg1 = await it.next()
        assert msg1 is not None
        assert msg1.value == b"msg1"

        msg2 = await it.next()
        assert msg2 is not None
        assert msg2.value == b"msg2"

        await it.close()

    async def test_execute_returns_none_after_close(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["t"])
        stream = ConsumerStream("stream", consumer)

        await producer.send("t", b"one")

        it = await stream.execute(None)

        msg = await it.next()
        assert msg is not None
        assert msg.value == b"one"

        # Close consumer so the iterator signals exhaustion
        await it.close()
        # Give the background task a moment to finish
        await asyncio.sleep(0.05)
        result = await it.next()
        assert result is None

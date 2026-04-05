"""Tests for BatchProducer."""

from __future__ import annotations

import asyncio

import pytest

from pykit_messaging.batch import BatchConfig, BatchProducer
from pykit_messaging.memory import InMemoryBroker
from pykit_messaging.types import Message


def _make_msg(topic: str = "batch-topic", value: bytes = b"payload") -> Message:
    return Message(key=None, value=value, topic=topic, partition=0, offset=0)


class TestBatchProducer:
    async def test_flush_on_max_size(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        config = BatchConfig(max_size=3, max_wait=60.0)
        batch = BatchProducer(producer, "batch-topic", config)

        try:
            await batch.send(_make_msg())
            await batch.send(_make_msg())

            # Queue should still be empty (not flushed yet)
            assert broker._queues["batch-topic"].qsize() == 0

            # Third message triggers flush
            await batch.send(_make_msg())
            assert broker._queues["batch-topic"].qsize() == 3
        finally:
            await batch.close()

    async def test_flush_on_max_bytes(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        config = BatchConfig(max_size=100, max_wait=60.0, max_bytes=10)
        batch = BatchProducer(producer, "batch-topic", config)

        try:
            # Each message has 7 bytes ("payload"), so 2 messages = 14 bytes > 10
            await batch.send(_make_msg())
            assert broker._queues["batch-topic"].qsize() == 0

            await batch.send(_make_msg())
            assert broker._queues["batch-topic"].qsize() == 2
        finally:
            await batch.close()

    async def test_manual_flush(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        config = BatchConfig(max_size=100, max_wait=60.0)
        batch = BatchProducer(producer, "batch-topic", config)

        try:
            await batch.send(_make_msg())
            await batch.send(_make_msg())

            assert broker._queues["batch-topic"].qsize() == 0

            await batch.flush()
            assert broker._queues["batch-topic"].qsize() == 2
        finally:
            await batch.close()

    async def test_close_flushes_remaining(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        config = BatchConfig(max_size=100, max_wait=60.0)
        batch = BatchProducer(producer, "batch-topic", config)

        await batch.send(_make_msg())
        await batch.send(_make_msg())

        assert broker._queues["batch-topic"].qsize() == 0

        await batch.close()
        assert broker._queues["batch-topic"].qsize() == 2

    async def test_time_flush(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        config = BatchConfig(max_size=100, max_wait=0.1)
        batch = BatchProducer(producer, "batch-topic", config)

        try:
            await batch.send(_make_msg())
            assert broker._queues["batch-topic"].qsize() == 0

            # Wait for periodic flush
            await asyncio.sleep(0.3)
            assert broker._queues["batch-topic"].qsize() == 1
        finally:
            await batch.close()

    async def test_concurrent_send(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        config = BatchConfig(max_size=5, max_wait=60.0)
        batch = BatchProducer(producer, "batch-topic", config)

        try:
            msgs = [_make_msg(value=f"msg-{i}".encode()) for i in range(20)]
            await asyncio.gather(*(batch.send(m) for m in msgs))

            # Some were flushed by size (4 batches of 5), rest might be buffered
            await batch.flush()

            assert broker._queues["batch-topic"].qsize() == 20
        finally:
            await batch.close()

    async def test_send_after_close_raises(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        batch = BatchProducer(producer, "batch-topic")

        await batch.close()

        with pytest.raises(RuntimeError, match="closed"):
            await batch.send(_make_msg())

    async def test_flush_empty_buffer_is_noop(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        config = BatchConfig(max_size=100, max_wait=60.0)
        batch = BatchProducer(producer, "batch-topic", config)

        try:
            await batch.flush()
            assert broker._queues["batch-topic"].qsize() == 0
        finally:
            await batch.close()

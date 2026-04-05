"""Tests for ConsumerRunner start/stop."""

from __future__ import annotations

import asyncio

import pytest

from pykit_messaging.handler import FuncHandler
from pykit_messaging.memory import InMemoryBroker
from pykit_messaging.runner import ConsumerRunner
from pykit_messaging.types import Message


class TestConsumerRunner:
    async def test_run_and_stop(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["t1"])

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        runner = ConsumerRunner(consumer, FuncHandler(handler))
        assert not runner.is_running

        # Start runner in background task
        task = asyncio.create_task(runner.run())
        await asyncio.sleep(0.05)
        assert runner.is_running

        await producer.send("t1", b"hello")
        await asyncio.sleep(0.1)

        await runner.stop()
        await task

        assert not runner.is_running
        assert len(received) == 1
        assert received[0].value == b"hello"

    async def test_run_twice_raises(self) -> None:
        broker = InMemoryBroker()
        consumer = broker.consumer(topics=["t1"])

        async def noop(msg: Message) -> None:
            pass

        runner = ConsumerRunner(consumer, FuncHandler(noop))
        task = asyncio.create_task(runner.run())
        await asyncio.sleep(0.05)

        with pytest.raises(RuntimeError, match="already running"):
            await runner.run()

        await runner.stop()
        await task

    async def test_stop_when_not_running_is_noop(self) -> None:
        broker = InMemoryBroker()
        consumer = broker.consumer(topics=["t1"])

        async def noop(msg: Message) -> None:
            pass

        runner = ConsumerRunner(consumer, FuncHandler(noop))
        await runner.stop()  # should not raise

    async def test_multiple_messages(self) -> None:
        broker = InMemoryBroker()
        producer = broker.producer()
        consumer = broker.consumer(topics=["t1"])

        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        runner = ConsumerRunner(consumer, FuncHandler(handler))
        task = asyncio.create_task(runner.run())
        await asyncio.sleep(0.05)

        for i in range(3):
            await producer.send("t1", f"msg-{i}".encode())

        await asyncio.sleep(0.2)
        await runner.stop()
        await task

        assert len(received) == 3

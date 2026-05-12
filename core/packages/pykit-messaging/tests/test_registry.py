from __future__ import annotations

import asyncio

import pytest

from pykit_errors import AppError
from pykit_messaging import BrokerConfig, InMemoryProducer, MemoryConfig, MessagingRegistry
from pykit_messaging.memory import register as register_memory
from pykit_messaging.types import Message


class DummyProducer:
    async def send(
        self,
        topic: str,
        value: bytes,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        pass

    async def send_event(self, topic: str, event: object) -> None:
        pass

    async def send_json(self, topic: str, data: object, key: str | None = None) -> None:
        pass

    async def send_batch(self, messages: list[Message]) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        pass


class DummyConsumer:
    async def subscribe(self, topics: list[str]) -> None:
        pass

    async def consume(self, handler: object) -> None:
        pass

    async def close(self) -> None:
        pass


def test_registry_starts_empty_and_has_no_side_effects() -> None:
    registry = MessagingRegistry()

    assert registry.producer_adapters() == []
    assert registry.consumer_adapters() == []
    with pytest.raises(AppError):
        registry.producer(BrokerConfig(adapter="kafka"))


def test_register_memory_adapter_is_config_free() -> None:
    registry = MessagingRegistry()

    register_memory(registry)

    assert registry.producer_adapters() == ["memory"]
    assert registry.consumer_adapters() == ["memory"]
    config = MemoryConfig(name="events", topics=["events"])
    assert registry.producer(config) is not None
    assert registry.consumer(config) is not None


def test_factories_are_invoked_with_creation_time_config() -> None:
    registry = MessagingRegistry()
    producer_configs: list[BrokerConfig] = []
    consumer_configs: list[BrokerConfig] = []

    registry.register_producer("dummy", lambda config: producer_configs.append(config) or DummyProducer())
    registry.register_consumer("dummy", lambda config: consumer_configs.append(config) or DummyConsumer())

    first = BrokerConfig(adapter="dummy", name="first")
    second = BrokerConfig(adapter="dummy", name="second")

    registry.producer(first)
    registry.consumer(second)

    assert producer_configs == [first]
    assert consumer_configs == [second]


@pytest.mark.asyncio
async def test_memory_registry_supports_multiple_configs_without_reregistration() -> None:
    registry = MessagingRegistry()
    register_memory(registry)

    first = MemoryConfig(name="first", topics=["events"])
    second = MemoryConfig(name="second", topics=["events"])

    first_producer = registry.producer(first)
    first_consumer = registry.consumer(first)
    second_producer = registry.producer(second)
    second_consumer = registry.consumer(second)

    assert isinstance(first_producer, InMemoryProducer)
    assert isinstance(second_producer, InMemoryProducer)

    await first_producer.send("events", b"first")
    await second_producer.send("events", b"second")

    first_received: list[Message] = []
    second_received: list[Message] = []

    async def first_handler(message: Message) -> None:
        first_received.append(message)
        await first_consumer.close()

    async def second_handler(message: Message) -> None:
        second_received.append(message)
        await second_consumer.close()

    await asyncio.gather(first_consumer.consume(first_handler), second_consumer.consume(second_handler))

    assert [message.value for message in first_received] == [b"first"]
    assert [message.value for message in second_received] == [b"second"]


def test_duplicate_registration_is_rejected() -> None:
    registry = MessagingRegistry()
    register_memory(registry)

    with pytest.raises(AppError):
        register_memory(registry)

"""Tests for EventPublisher facade."""

from __future__ import annotations

import pytest

from pykit_messaging.event_publisher import EventPublisher
from pykit_messaging.types import Event


class MockProducer:
    """Captures send_event calls for assertion."""

    def __init__(self) -> None:
        self.events: list[tuple[str, Event]] = []

    async def send(
        self, topic: str, value: bytes, key: str | None = None, headers: dict[str, str] | None = None
    ) -> None:
        pass

    async def send_event(self, topic: str, event: Event) -> None:
        self.events.append((topic, event))

    async def send_json(self, topic: str, data: object, key: str | None = None) -> None:
        pass

    async def send_batch(self, messages: list) -> None:
        pass

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        pass


@pytest.mark.asyncio
async def test_publish_creates_envelope() -> None:
    mock = MockProducer()
    publisher = EventPublisher(mock, "test-service")

    await publisher.publish("my.topic", "payload.created", {"name": "hello", "value": 42})

    assert len(mock.events) == 1
    topic, event = mock.events[0]
    assert topic == "my.topic"
    assert event.type == "payload.created"
    assert event.source == "test-service"
    assert event.id  # non-empty UUID
    assert event.version == "1.0"
    assert event.data == {"name": "hello", "value": 42}


@pytest.mark.asyncio
async def test_publish_keyed_sets_subject() -> None:
    mock = MockProducer()
    publisher = EventPublisher(mock, "order-svc")

    await publisher.publish_keyed("orders", "order.placed", {"id": "123"}, key="order-123")

    _topic, event = mock.events[0]
    assert event.subject == "order-123"
    assert event.type == "order.placed"
    assert event.source == "order-svc"


@pytest.mark.asyncio
async def test_publish_batch_creates_multiple_envelopes() -> None:
    mock = MockProducer()
    publisher = EventPublisher(mock, "batch-svc")

    items = [{"name": "a"}, {"name": "b"}, {"name": "c"}]
    await publisher.publish_batch("items", "item.created", items)

    assert len(mock.events) == 3
    ids = set()
    for topic, event in mock.events:
        assert topic == "items"
        assert event.type == "item.created"
        assert event.source == "batch-svc"
        ids.add(event.id)
    assert len(ids) == 3  # unique IDs


def test_source_accessor() -> None:
    mock = MockProducer()
    publisher = EventPublisher(mock, "my-service")
    assert publisher.source == "my-service"


def test_producer_accessor() -> None:
    mock = MockProducer()
    publisher = EventPublisher(mock, "my-service")
    assert publisher.producer is mock

"""High-level event publishing facade.

:class:`EventPublisher` wraps any :class:`~pykit_messaging.protocols.MessageProducer`
with a pre-configured *source* name so callers only provide the topic,
event type, and payload.  The envelope (UUID, timestamp, version) is
filled in automatically.

Example::

    publisher = EventPublisher(producer, "order-service")

    await publisher.publish("orders.placed", "order.placed", {"order_id": "abc", "total": 99.99})
    await publisher.publish_keyed("orders.placed", "order.placed", {"order_id": "def"}, key="def")
"""

from __future__ import annotations

from pykit_messaging.protocols import MessageProducer
from pykit_messaging.types import Event, JsonValue


class EventPublisher:
    """Facade that simplifies event publishing by automatically constructing
    :class:`~pykit_messaging.types.Event` envelopes from arbitrary payloads.

    Configured once with a *source* name (typically the service name) and an
    underlying :class:`~pykit_messaging.protocols.MessageProducer`.  Every call
    to :meth:`publish` or :meth:`publish_keyed` creates a fresh envelope.
    """

    __slots__ = ("_producer", "_source")

    def __init__(self, producer: MessageProducer, source: str) -> None:
        self._producer = producer
        self._source = source

    async def publish(
        self,
        topic: str,
        event_type: str,
        data: JsonValue = None,
    ) -> None:
        """Publish *data* as a domain event.

        Builds an :class:`Event` with a fresh UUID, UTC timestamp,
        the configured source, and the given *event_type*.
        """
        event = Event(type=event_type, source=self._source, data=data)
        await self._producer.send_event(topic, event)

    async def publish_keyed(
        self,
        topic: str,
        event_type: str,
        data: JsonValue,
        key: str,
    ) -> None:
        """Publish *data* with an explicit partition key.

        Sets ``Event.subject`` to *key* so messaging adapters can use it
        for ordering guarantees.
        """
        event = Event(type=event_type, source=self._source, subject=key, data=data)
        await self._producer.send_event(topic, event)

    async def publish_batch(
        self,
        topic: str,
        event_type: str,
        items: list[JsonValue],
    ) -> None:
        """Publish multiple items, each wrapped in its own event envelope."""
        for item in items:
            event = Event(type=event_type, source=self._source, data=item)
            await self._producer.send_event(topic, event)

    @property
    def source(self) -> str:
        """The configured source name."""
        return self._source

    @property
    def producer(self) -> MessageProducer:
        """The underlying producer."""
        return self._producer

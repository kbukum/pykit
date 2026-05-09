"""Transport-agnostic messaging protocols."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pykit_messaging.types import Event, JsonValue, Message, MessageHandler


@runtime_checkable
class MessageProducer(Protocol):
    """Transport-agnostic message producer."""

    async def send(
        self,
        topic: str,
        value: bytes,
        key: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        """Send raw bytes to the given topic."""

    async def send_event(self, topic: str, event: Event) -> None:
        """Serialize and send an event to the given topic."""

    async def send_json(self, topic: str, data: JsonValue, key: str | None = None) -> None:
        """Serialize and send JSON-compatible data to the given topic."""

    async def send_batch(self, messages: list[Message]) -> None:
        """Send a batch of messages."""

    async def flush(self) -> None:
        """Flush any buffered messages to the broker."""

    async def close(self) -> None:
        """Release producer resources and close broker connections."""


@runtime_checkable
class MessageConsumer(Protocol):
    """Transport-agnostic message consumer."""

    async def subscribe(self, topics: list[str]) -> None:
        """Subscribe the consumer to the given topics."""

    async def consume(self, handler: MessageHandler) -> None:
        """Consume messages and dispatch each one to the handler."""

    async def close(self) -> None:
        """Stop consumption and release consumer resources."""


@runtime_checkable
class ControllableConsumer(Protocol):
    """Optional pause/resume capability for adapters that support it."""

    async def pause(self) -> None:
        """Pause message delivery without closing the consumer."""

    async def resume(self) -> None:
        """Resume message delivery after a pause."""

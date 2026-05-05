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
    ) -> None: ...

    async def send_event(self, topic: str, event: Event) -> None: ...

    async def send_json(self, topic: str, data: JsonValue, key: str | None = None) -> None: ...

    async def send_batch(self, messages: list[Message]) -> None: ...

    async def flush(self) -> None: ...

    async def close(self) -> None: ...


@runtime_checkable
class MessageConsumer(Protocol):
    """Transport-agnostic message consumer."""

    async def subscribe(self, topics: list[str]) -> None: ...

    async def consume(self, handler: MessageHandler) -> None: ...

    async def close(self) -> None: ...


@runtime_checkable
class ControllableConsumer(Protocol):
    """Optional pause/resume capability for adapters that support it."""

    async def pause(self) -> None: ...

    async def resume(self) -> None: ...

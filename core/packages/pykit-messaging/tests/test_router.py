"""Tests for MessageRouter."""

from __future__ import annotations

import asyncio

from pykit_messaging.handler import FuncHandler, MessageHandlerProtocol
from pykit_messaging.router import MessageRouter
from pykit_messaging.types import Message


def _make_msg(topic: str = "test", value: bytes = b"payload") -> Message:
    return Message(key=None, value=value, topic=topic, partition=0, offset=0)


def _collecting_handler(store: list[Message]) -> MessageHandlerProtocol:
    async def _handle(msg: Message) -> None:
        store.append(msg)

    return FuncHandler(_handle)


class TestMessageRouter:
    async def test_exact_match(self) -> None:
        received: list[Message] = []
        router = MessageRouter()
        router.handle("orders.created", _collecting_handler(received))

        handler = router.as_handler()
        msg = _make_msg(topic="orders.created")
        await handler.handle(msg)

        assert len(received) == 1
        assert received[0] is msg

    async def test_wildcard_match(self) -> None:
        received: list[Message] = []
        router = MessageRouter()
        router.handle("content.*", _collecting_handler(received))

        handler = router.as_handler()
        await handler.handle(_make_msg(topic="content.uploaded"))
        await handler.handle(_make_msg(topic="content.deleted"))

        assert len(received) == 2
        assert received[0].topic == "content.uploaded"
        assert received[1].topic == "content.deleted"

    async def test_first_match_wins(self) -> None:
        first: list[Message] = []
        second: list[Message] = []
        router = MessageRouter()
        router.handle("orders.*", _collecting_handler(first))
        router.handle("orders.created", _collecting_handler(second))

        handler = router.as_handler()
        await handler.handle(_make_msg(topic="orders.created"))

        assert len(first) == 1
        assert len(second) == 0

    async def test_default_handler(self) -> None:
        default_received: list[Message] = []
        router = MessageRouter()
        router.handle("orders.*", _collecting_handler([]))
        router.default(_collecting_handler(default_received))

        handler = router.as_handler()
        await handler.handle(_make_msg(topic="users.created"))

        assert len(default_received) == 1
        assert default_received[0].topic == "users.created"

    async def test_no_match_no_default(self) -> None:
        """Unmatched messages with no default handler should not raise."""
        router = MessageRouter()
        router.handle("orders.*", _collecting_handler([]))

        handler = router.as_handler()
        await handler.handle(_make_msg(topic="users.created"))

    async def test_fluent_chaining(self) -> None:
        r1: list[Message] = []
        r2: list[Message] = []
        dflt: list[Message] = []

        router = (
            MessageRouter()
            .handle("a.*", _collecting_handler(r1))
            .handle("b.*", _collecting_handler(r2))
            .default(_collecting_handler(dflt))
        )

        handler = router.as_handler()
        await handler.handle(_make_msg(topic="a.1"))
        await handler.handle(_make_msg(topic="b.2"))
        await handler.handle(_make_msg(topic="c.3"))

        assert len(r1) == 1
        assert len(r2) == 1
        assert len(dflt) == 1

    async def test_concurrent_routing(self) -> None:
        received: list[Message] = []
        router = MessageRouter()
        router.handle("topic.*", _collecting_handler(received))

        handler = router.as_handler()
        msgs = [_make_msg(topic=f"topic.{i}") for i in range(20)]
        await asyncio.gather(*(handler.handle(m) for m in msgs))

        assert len(received) == 20

    async def test_as_handler_satisfies_protocol(self) -> None:
        router = MessageRouter()
        handler = router.as_handler()
        assert isinstance(handler, MessageHandlerProtocol)

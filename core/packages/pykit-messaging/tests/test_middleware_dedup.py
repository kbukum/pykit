"""Tests for dedup middleware."""

from __future__ import annotations

import time
from unittest.mock import patch

from pykit_messaging.handler import FuncHandler, MessageHandlerProtocol
from pykit_messaging.middleware.dedup import DedupConfig, DedupHandler, dedup
from pykit_messaging.types import Message


def _make_msg(
    topic: str = "test",
    offset: int = 0,
    headers: dict[str, str] | None = None,
) -> Message:
    return Message(
        key=None,
        value=b"payload",
        topic=topic,
        partition=0,
        offset=offset,
        headers=headers or {},
    )


def _collecting_handler(store: list[Message]) -> FuncHandler:
    async def _handle(msg: Message) -> None:
        store.append(msg)

    return FuncHandler(_handle)


class TestDedupHandler:
    async def test_duplicate_skipped_by_message_id(self) -> None:
        received: list[Message] = []
        handler = DedupHandler(_collecting_handler(received))

        msg1 = _make_msg(headers={"message-id": "abc-123"})
        msg2 = _make_msg(headers={"message-id": "abc-123"})

        await handler.handle(msg1)
        await handler.handle(msg2)

        assert len(received) == 1

    async def test_unique_messages_pass_through(self) -> None:
        received: list[Message] = []
        handler = DedupHandler(_collecting_handler(received))

        msg1 = _make_msg(headers={"message-id": "id-1"})
        msg2 = _make_msg(headers={"message-id": "id-2"})
        msg3 = _make_msg(headers={"message-id": "id-3"})

        await handler.handle(msg1)
        await handler.handle(msg2)
        await handler.handle(msg3)

        assert len(received) == 3

    async def test_fallback_to_offset_key(self) -> None:
        received: list[Message] = []
        handler = DedupHandler(_collecting_handler(received))

        # No message-id header: uses topic:partition:offset
        msg1 = _make_msg(offset=1)
        msg2 = _make_msg(offset=1)  # same key
        msg3 = _make_msg(offset=2)  # different key

        await handler.handle(msg1)
        await handler.handle(msg2)
        await handler.handle(msg3)

        assert len(received) == 2

    async def test_custom_key_func(self) -> None:
        received: list[Message] = []
        config = DedupConfig(key_func=lambda m: m.value.decode())
        handler = DedupHandler(_collecting_handler(received), config)

        msg1 = Message(key=None, value=b"same", topic="t", partition=0, offset=0)
        msg2 = Message(key=None, value=b"same", topic="t", partition=0, offset=1)
        msg3 = Message(key=None, value=b"different", topic="t", partition=0, offset=2)

        await handler.handle(msg1)
        await handler.handle(msg2)
        await handler.handle(msg3)

        assert len(received) == 2

    async def test_ttl_expiry(self) -> None:
        received: list[Message] = []
        config = DedupConfig(ttl=1.0)
        handler = DedupHandler(_collecting_handler(received), config)

        msg = _make_msg(headers={"message-id": "ttl-test"})
        await handler.handle(msg)
        assert len(received) == 1

        # Simulate time passing beyond TTL
        base_time = time.monotonic()
        with patch("pykit_messaging.middleware.dedup.time") as mock_time:
            mock_time.monotonic.return_value = base_time + 2.0
            msg2 = _make_msg(headers={"message-id": "ttl-test"})
            await handler.handle(msg2)

        assert len(received) == 2

    async def test_window_eviction(self) -> None:
        received: list[Message] = []
        config = DedupConfig(window_size=3, ttl=300.0)
        handler = DedupHandler(_collecting_handler(received), config)

        # Fill window with 3 entries
        for i in range(3):
            await handler.handle(_make_msg(headers={"message-id": f"msg-{i}"}))
        assert len(received) == 3

        # Add a 4th — should evict the oldest ("msg-0")
        await handler.handle(_make_msg(headers={"message-id": "msg-3"}))
        assert len(received) == 4

        # Now "msg-0" should have been evicted, so it passes through again
        await handler.handle(_make_msg(headers={"message-id": "msg-0"}))
        assert len(received) == 5

        # But "msg-1" should still be in window (it was 2nd)
        # After eviction: window should have msg-1, msg-2, msg-3, then msg-0 added -> evicts msg-1
        # Actually: after msg-3, window = [msg-1, msg-2, msg-3] (msg-0 evicted)
        # After msg-0 again, window = [msg-2, msg-3, msg-0] (msg-1 evicted)
        await handler.handle(_make_msg(headers={"message-id": "msg-1"}))
        assert len(received) == 6

    async def test_dedup_middleware_factory(self) -> None:
        received: list[Message] = []
        inner = _collecting_handler(received)
        middleware = dedup()
        wrapped = middleware(inner)

        msg1 = _make_msg(headers={"message-id": "factory-1"})
        msg2 = _make_msg(headers={"message-id": "factory-1"})

        await wrapped.handle(msg1)
        await wrapped.handle(msg2)

        assert len(received) == 1

    async def test_dedup_satisfies_protocol(self) -> None:
        inner = _collecting_handler([])
        handler = DedupHandler(inner)
        assert isinstance(handler, MessageHandlerProtocol)

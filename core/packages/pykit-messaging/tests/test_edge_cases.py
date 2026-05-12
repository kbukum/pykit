"""Edge case and gap coverage tests for pykit-messaging."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

import pytest

from pykit_messaging.config import BrokerConfig
from pykit_messaging.errors import (
    GENERIC_CONNECTION_PATTERNS,
    is_connection_error,
    is_retryable_error,
)
from pykit_messaging.handler import (
    FuncHandler,
    MessageHandlerProtocol,
    chain_handlers,
)
from pykit_messaging.memory import InMemoryBroker
from pykit_messaging.router import MessageRouter
from pykit_messaging.translator import JsonTranslator
from pykit_messaging.types import Event, Message


def _make_msg(
    topic: str = "t",
    key: str | None = "k",
    value: bytes = b"v",
    partition: int = 0,
    offset: int = 0,
) -> Message:
    return Message(key=key, value=value, topic=topic, partition=partition, offset=offset)


# ── Event edge cases ──────────────────────────────────────────────────


class TestEventEdgeCases:
    def test_event_from_json_minimal_fields(self):
        """from_json with only required fields, defaults applied for optionals."""
        minimal = {
            "id": "abc-123",
            "type": "test.event",
            "source": "unit-test",
            "timestamp": datetime.now(UTC).isoformat(),
        }
        raw = json.dumps(minimal).encode()
        event = Event.from_json(raw)
        assert event.id == "abc-123"
        assert event.type == "test.event"
        assert event.source == "unit-test"
        assert event.subject == ""
        assert event.content_type == "application/json"
        assert event.version == "1.0"
        assert event.data is None

    def test_event_from_json_invalid_bytes_raises(self):
        """from_json with invalid JSON bytes raises error."""
        with pytest.raises((json.JSONDecodeError, ValueError)):
            Event.from_json(b"not-json{{{")

    def test_event_to_json_roundtrip_with_nested_data(self):
        """Event with complex nested data survives JSON roundtrip."""
        nested = {"users": [{"name": "Alice", "roles": ["admin", "editor"]}], "count": 42}
        original = Event(type="complex", source="test", data=nested)
        restored = Event.from_json(original.to_json())
        assert restored.data == nested
        assert restored.type == original.type
        assert restored.source == original.source

    def test_event_unique_ids(self):
        """Each Event gets a unique UUID by default."""
        events = [Event(type="t", source="s") for _ in range(50)]
        ids = {e.id for e in events}
        assert len(ids) == 50

    def test_event_timestamp_is_utc(self):
        """Default event timestamp uses UTC."""
        event = Event(type="t", source="s")
        assert event.timestamp.tzinfo is UTC


# ── Error Classification Edge Cases ─────────────────────────────────


class TestErrorEdgeCases:
    def test_is_connection_error_none_returns_false(self):
        """None error returns False."""
        assert is_connection_error(None) is False

    def test_is_retryable_error_none_returns_false(self):
        """None error returns False for retryable check."""
        assert is_retryable_error(None) is False

    def test_is_connection_error_with_extra_patterns(self):
        """Custom extra_patterns are checked."""
        err = RuntimeError("custom kafka broker unavailable")
        assert is_connection_error(err) is False
        assert is_connection_error(err, extra_patterns=("broker unavailable",)) is True

    def test_is_retryable_error_connection_errors_are_retryable(self):
        """Connection errors are also retryable."""
        err = OSError("connection refused")
        assert is_connection_error(err) is True
        assert is_retryable_error(err) is True

    def test_is_retryable_error_with_custom_patterns(self):
        """Extra retryable patterns work."""
        err = RuntimeError("throttled by server")
        assert is_retryable_error(err) is False
        assert is_retryable_error(err, extra_retryable_patterns=("throttled",)) is True

    def test_is_connection_error_case_insensitive(self):
        """Error matching is case-insensitive."""
        err = RuntimeError("CONNECTION REFUSED by host")
        assert is_connection_error(err) is True

    def test_is_connection_error_all_generic_patterns(self):
        """Every generic pattern is actually recognized."""
        for pattern in GENERIC_CONNECTION_PATTERNS:
            err = RuntimeError(f"something {pattern} happened")
            assert is_connection_error(err) is True, f"Pattern '{pattern}' not matched"

    def test_non_matching_error_returns_false(self):
        """Unrelated error message is not classified as connection or retryable."""
        err = ValueError("invalid argument format")
        assert is_connection_error(err) is False
        assert is_retryable_error(err) is False


# ── Config Edge Cases ────────────────────────────────────────────────


class TestConfigEdgeCases:
    def test_broker_config_defaults(self):
        """BrokerConfig has expected default values."""
        cfg = BrokerConfig()
        assert cfg.name == "memory"
        assert cfg.enabled is True
        assert not hasattr(cfg, "brokers")
        assert cfg.retries == 3
        assert cfg.request_timeout_ms == 30000

    def test_broker_config_custom_values(self):
        """BrokerConfig accepts custom values."""
        cfg = BrokerConfig(
            name="prod",
            enabled=False,
            retries=5,
            request_timeout_ms=60000,
        )
        assert cfg.name == "prod"
        assert cfg.enabled is False
        assert not hasattr(cfg, "brokers")
        assert cfg.retries == 5
        assert cfg.request_timeout_ms == 60000

    def test_broker_config_has_no_adapter_connection_fields(self):
        """Core BrokerConfig does not carry broker-specific endpoint fields."""
        cfg = BrokerConfig()
        assert not hasattr(cfg, "brokers")
        assert cfg.consumer_group == ""
        assert cfg.topics == []
        assert cfg.subscriptions == []


# ── Router Edge Cases ────────────────────────────────────────────────


class TestRouterEdgeCases:
    async def test_router_multiple_wildcard_patterns(self):
        """Router with multiple wildcard patterns dispatches correctly."""
        order_calls: list[str] = []
        user_calls: list[str] = []

        async def on_order(msg: Message) -> None:
            order_calls.append(msg.topic)

        async def on_user(msg: Message) -> None:
            user_calls.append(msg.topic)

        handler = (
            MessageRouter()
            .handle("orders.*", FuncHandler(on_order))
            .handle("users.*", FuncHandler(on_user))
            .as_handler()
        )

        await handler.handle(_make_msg(topic="orders.created"))
        await handler.handle(_make_msg(topic="users.deleted"))
        await handler.handle(_make_msg(topic="orders.updated"))

        assert order_calls == ["orders.created", "orders.updated"]
        assert user_calls == ["users.deleted"]

    async def test_router_concurrent_dispatch(self):
        """Router handles concurrent dispatches correctly."""
        calls: list[str] = []

        async def on_msg(msg: Message) -> None:
            await asyncio.sleep(0.01)
            calls.append(msg.topic)

        handler = MessageRouter().handle("*", FuncHandler(on_msg)).as_handler()

        tasks = [handler.handle(_make_msg(topic=f"topic-{i}")) for i in range(10)]
        await asyncio.gather(*tasks)

        assert len(calls) == 10
        assert set(calls) == {f"topic-{i}" for i in range(10)}

    async def test_router_empty_topic_with_default(self):
        """Router with empty string topic works with default handler."""
        default_calls: list[str] = []

        async def on_default(msg: Message) -> None:
            default_calls.append(msg.topic)

        handler = MessageRouter().default(FuncHandler(on_default)).as_handler()
        await handler.handle(_make_msg(topic=""))

        assert default_calls == [""]

    async def test_router_no_routes_no_default_no_error(self):
        """Router with no routes and no default doesn't raise, just logs."""
        handler = MessageRouter().as_handler()
        await handler.handle(_make_msg(topic="anything"))


# ── Handler Edge Cases ───────────────────────────────────────────────


class TestHandlerEdgeCases:
    async def test_func_handler_exception_propagates(self):
        """Exceptions in FuncHandler propagate to caller."""

        async def failing(msg: Message) -> None:
            raise ValueError("handler boom")

        handler = FuncHandler(failing)
        with pytest.raises(ValueError, match="handler boom"):
            await handler.handle(_make_msg())

    async def test_chain_multiple_middlewares_ordering(self):
        """Multiple middlewares execute in correct order (outermost first)."""
        call_order: list[str] = []

        async def base_handler(msg: Message) -> None:
            call_order.append("base")

        def make_middleware(name: str):
            def middleware(inner: MessageHandlerProtocol) -> MessageHandlerProtocol:
                async def wrapper(msg: Message) -> None:
                    call_order.append(f"{name}-before")
                    await inner.handle(msg)
                    call_order.append(f"{name}-after")

                return FuncHandler(wrapper)

            return middleware

        chained = chain_handlers(
            FuncHandler(base_handler),
            make_middleware("m1"),
            make_middleware("m2"),
        )
        await chained.handle(_make_msg())

        # m2 is outermost: m2-before, m1-before, base, m1-after, m2-after
        assert call_order == ["m2-before", "m1-before", "base", "m1-after", "m2-after"]

    def test_func_handler_satisfies_protocol(self):
        """FuncHandler satisfies MessageHandlerProtocol."""

        async def noop(msg: Message) -> None:
            pass

        handler = FuncHandler(noop)
        assert isinstance(handler, MessageHandlerProtocol)


# ── Translator Edge Cases ────────────────────────────────────────────


class TestTranslatorEdgeCases:
    def test_json_translator_unicode(self):
        """Translator handles unicode and special characters."""
        t = JsonTranslator()
        data = {"greeting": "こんにちは", "emoji": "🚀", "accents": "café"}
        result = t.deserialize(t.serialize(data))
        assert result == data

    def test_json_translator_empty_dict(self):
        """Serializing empty dict works."""
        t = JsonTranslator()
        raw = t.serialize({})
        assert t.deserialize(raw) == {}

    def test_json_translator_invalid_bytes_raises(self):
        """Deserializing invalid bytes raises error."""
        t = JsonTranslator()
        with pytest.raises((json.JSONDecodeError, ValueError)):
            t.deserialize(b"<<not json>>")

    def test_json_translator_datetime_uses_isoformat(self):
        """Datetime values use the shared JSON codec's ISO-8601 representation."""
        t = JsonTranslator()
        now = datetime.now(UTC)
        data = {"ts": now}
        raw = t.serialize(data)
        result = t.deserialize(raw)
        assert result["ts"] == now.isoformat()


# ── InMemoryBroker Edge Cases ────────────────────────────────────────


class TestInMemoryBrokerEdgeCases:
    async def test_broker_reset_clears_everything(self):
        """reset() clears messages and topics."""
        broker = InMemoryBroker()
        producer = broker.producer()
        await producer.send("topic1", b"hello")
        assert broker.message_count("topic1") == 1

        broker.reset()
        assert broker.message_count("topic1") == 0
        assert broker.all_messages() == []

    async def test_broker_multiple_topics_isolation(self):
        """Messages to different topics are isolated."""
        broker = InMemoryBroker()
        producer = broker.producer()
        await producer.send("topic-a", b"a1")
        await producer.send("topic-a", b"a2")
        await producer.send("topic-b", b"b1")

        assert broker.message_count("topic-a") == 2
        assert broker.message_count("topic-b") == 1
        assert len(broker.all_messages()) == 3

    async def test_broker_send_json_roundtrip(self):
        """send_json produces valid JSON that can be decoded."""
        broker = InMemoryBroker()
        producer = broker.producer()
        await producer.send_json("json-topic", {"key": "value", "num": 42})

        msgs = broker.messages("json-topic")
        assert len(msgs) == 1
        decoded = json.loads(msgs[0].value)
        assert decoded == {"key": "value", "num": 42}

    async def test_broker_topics_returns_sorted(self):
        """topics() returns sorted unique topic names."""
        broker = InMemoryBroker()
        producer = broker.producer()
        await producer.send("zebra", b"z")
        await producer.send("alpha", b"a")
        await producer.send("middle", b"m")

        assert broker.topics() == ["alpha", "middle", "zebra"]

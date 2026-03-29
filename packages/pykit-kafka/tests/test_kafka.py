"""Tests for pykit-kafka — all aiokafka interactions are mocked."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from pykit_kafka import (
    Event,
    KafkaComponent,
    KafkaConfig,
    KafkaConsumer,
    KafkaProducer,
    Message,
    is_connection_error,
    is_retryable_error,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestKafkaConfig:
    def test_defaults(self):
        cfg = KafkaConfig()
        assert cfg.name == "kafka"
        assert cfg.brokers == ["localhost:9092"]
        assert cfg.group_id == ""
        assert cfg.topics == []
        assert cfg.enabled is True
        assert cfg.security_protocol == "PLAINTEXT"
        assert cfg.sasl_mechanism == ""
        assert cfg.compression_type == "snappy"
        assert cfg.auto_offset_reset == "earliest"

    def test_custom_values(self):
        cfg = KafkaConfig(
            name="my-kafka",
            brokers=["broker1:9092", "broker2:9092"],
            group_id="test-group",
            topics=["topic-a", "topic-b"],
            security_protocol="SASL_SSL",
            sasl_mechanism="PLAIN",
            sasl_username="user",
            sasl_password="pass",
        )
        assert cfg.name == "my-kafka"
        assert len(cfg.brokers) == 2
        assert cfg.group_id == "test-group"
        assert cfg.sasl_mechanism == "PLAIN"


# ---------------------------------------------------------------------------
# Message / Event types
# ---------------------------------------------------------------------------


class TestMessage:
    def test_fields(self):
        now = datetime.now(UTC)
        msg = Message(
            key="k1",
            value=b"hello",
            topic="t",
            partition=0,
            offset=42,
            timestamp=now,
            headers={"h": "v"},
        )
        assert msg.key == "k1"
        assert msg.value == b"hello"
        assert msg.topic == "t"
        assert msg.partition == 0
        assert msg.offset == 42
        assert msg.timestamp == now
        assert msg.headers == {"h": "v"}

    def test_defaults(self):
        msg = Message(key=None, value=b"", topic="t", partition=0, offset=0)
        assert msg.timestamp is None
        assert msg.headers == {}


class TestEvent:
    def test_auto_fields(self):
        evt = Event(type="user.created", source="svc-a")
        assert evt.id  # non-empty UUID
        assert evt.timestamp <= datetime.now(UTC)
        assert evt.subject == ""
        assert evt.data is None

    def test_roundtrip_json(self):
        evt = Event(type="order.placed", source="shop", subject="order-1", data={"total": 42})
        raw = evt.to_json()
        restored = Event.from_json(raw)
        assert restored.id == evt.id
        assert restored.type == evt.type
        assert restored.source == evt.source
        assert restored.subject == evt.subject
        assert restored.data == evt.data

    def test_to_json_format(self):
        evt = Event(type="t", source="s")
        d = json.loads(evt.to_json())
        assert set(d.keys()) == {"id", "type", "source", "timestamp", "subject", "data"}


# ---------------------------------------------------------------------------
# Producer
# ---------------------------------------------------------------------------


class TestProducer:
    async def test_start_stop(self):
        with patch("pykit_kafka.producer.AIOKafkaProducer") as MockProducer:
            mock_instance = AsyncMock()
            MockProducer.return_value = mock_instance

            producer = KafkaProducer(KafkaConfig())
            await producer.start()
            mock_instance.start.assert_awaited_once()

            await producer.stop()
            mock_instance.stop.assert_awaited_once()

    async def test_send(self):
        with patch("pykit_kafka.producer.AIOKafkaProducer") as MockProducer:
            mock_instance = AsyncMock()
            MockProducer.return_value = mock_instance

            producer = KafkaProducer(KafkaConfig())
            await producer.start()

            await producer.send("my-topic", b"payload", key="k1", headers={"h": "v"})
            mock_instance.send_and_wait.assert_awaited_once_with(
                "my-topic",
                value=b"payload",
                key=b"k1",
                headers=[("h", b"v")],
            )

    async def test_send_not_started_raises(self):
        producer = KafkaProducer(KafkaConfig())
        with pytest.raises(RuntimeError, match="not started"):
            await producer.send("t", b"v")

    async def test_send_event(self):
        with patch("pykit_kafka.producer.AIOKafkaProducer") as MockProducer:
            mock_instance = AsyncMock()
            MockProducer.return_value = mock_instance

            producer = KafkaProducer(KafkaConfig())
            await producer.start()

            evt = Event(type="test.event", source="test")
            await producer.send_event("events", evt)
            mock_instance.send_and_wait.assert_awaited_once()
            call_kwargs = mock_instance.send_and_wait.call_args
            assert call_kwargs[0][0] == "events"
            assert b"test.event" in call_kwargs[1]["value"]

    async def test_send_json(self):
        with patch("pykit_kafka.producer.AIOKafkaProducer") as MockProducer:
            mock_instance = AsyncMock()
            MockProducer.return_value = mock_instance

            producer = KafkaProducer(KafkaConfig())
            await producer.start()

            await producer.send_json("json-topic", {"foo": "bar"}, key="k")
            call_kwargs = mock_instance.send_and_wait.call_args
            assert json.loads(call_kwargs[1]["value"]) == {"foo": "bar"}

    async def test_sasl_config(self):
        cfg = KafkaConfig(
            sasl_mechanism="PLAIN",
            sasl_username="user",
            sasl_password="pass",
            security_protocol="SASL_SSL",
        )
        with patch("pykit_kafka.producer.AIOKafkaProducer") as MockProducer:
            mock_instance = AsyncMock()
            MockProducer.return_value = mock_instance

            producer = KafkaProducer(cfg)
            await producer.start()
            call_kwargs = MockProducer.call_args[1]
            assert call_kwargs["sasl_mechanism"] == "PLAIN"
            assert call_kwargs["sasl_plain_username"] == "user"
            assert call_kwargs["sasl_plain_password"] == "pass"


# ---------------------------------------------------------------------------
# Consumer
# ---------------------------------------------------------------------------


class TestConsumer:
    async def test_start_stop(self):
        with patch("pykit_kafka.consumer.AIOKafkaConsumer") as MockConsumer:
            mock_instance = AsyncMock()
            MockConsumer.return_value = mock_instance

            consumer = KafkaConsumer(KafkaConfig(topics=["t1"]))
            await consumer.start()
            mock_instance.start.assert_awaited_once()

            await consumer.stop()
            mock_instance.stop.assert_awaited_once()

    async def test_consume(self):
        with patch("pykit_kafka.consumer.AIOKafkaConsumer") as MockConsumer:
            record = MagicMock()
            record.key = b"k"
            record.value = b"v"
            record.topic = "t"
            record.partition = 0
            record.offset = 1
            record.headers = [(b"h", b"val")]

            mock_instance = AsyncMock()

            async def _aiter(*_args, **_kwargs):
                yield record

            mock_instance.__aiter__ = _aiter
            MockConsumer.return_value = mock_instance

            consumer = KafkaConsumer(KafkaConfig(topics=["t"]))
            await consumer.start()

            received: list[Message] = []

            async def handler(msg: Message) -> None:
                received.append(msg)

            await consumer.consume(handler)
            assert len(received) == 1
            assert received[0].key == "k"
            assert received[0].value == b"v"
            assert received[0].headers == {"h": "val"}

    async def test_consume_not_started_raises(self):
        consumer = KafkaConsumer(KafkaConfig())
        with pytest.raises(RuntimeError, match="not started"):
            await consumer.consume(AsyncMock())

    async def test_sasl_config(self):
        """Cover consumer.py lines 32-34: SASL kwargs are passed."""
        cfg = KafkaConfig(
            topics=["t1"],
            sasl_mechanism="PLAIN",
            sasl_username="user",
            sasl_password="pass",
            security_protocol="SASL_SSL",
        )
        with patch("pykit_kafka.consumer.AIOKafkaConsumer") as MockConsumer:
            mock_instance = AsyncMock()
            MockConsumer.return_value = mock_instance

            consumer = KafkaConsumer(cfg)
            await consumer.start()
            call_kwargs = MockConsumer.call_args[1]
            assert call_kwargs["sasl_mechanism"] == "PLAIN"
            assert call_kwargs["sasl_plain_username"] == "user"
            assert call_kwargs["sasl_plain_password"] == "pass"
            await consumer.stop()

    async def test_consume_events(self):
        evt = Event(type="x", source="s", data={"a": 1})
        with patch("pykit_kafka.consumer.AIOKafkaConsumer") as MockConsumer:
            record = MagicMock()
            record.key = None
            record.value = evt.to_json()
            record.topic = "events"
            record.partition = 0
            record.offset = 0
            record.headers = None

            mock_instance = AsyncMock()

            async def _aiter(*_args, **_kwargs):
                yield record

            mock_instance.__aiter__ = _aiter
            MockConsumer.return_value = mock_instance

            consumer = KafkaConsumer(KafkaConfig(topics=["events"]))
            await consumer.start()

            received: list[Event] = []

            async def handler(e: Event) -> None:
                received.append(e)

            await consumer.consume_events(handler)
            assert len(received) == 1
            assert received[0].type == "x"
            assert received[0].data == {"a": 1}


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


class TestErrors:
    def test_none_is_not_error(self):
        assert is_connection_error(None) is False
        assert is_retryable_error(None) is False

    @pytest.mark.parametrize(
        "msg",
        [
            "connection refused",
            "Connection Reset by peer",
            "broker not available",
            "leader not available",
        ],
    )
    def test_connection_errors(self, msg: str):
        assert is_connection_error(Exception(msg)) is True
        assert is_retryable_error(Exception(msg)) is True

    @pytest.mark.parametrize(
        "msg",
        [
            "request timed out",
            "temporary failure",
            "not enough replicas",
        ],
    )
    def test_retryable_non_connection(self, msg: str):
        assert is_connection_error(Exception(msg)) is False
        assert is_retryable_error(Exception(msg)) is True

    def test_non_retryable(self):
        err = Exception("invalid topic name")
        assert is_retryable_error(err) is False


# ---------------------------------------------------------------------------
# Component lifecycle
# ---------------------------------------------------------------------------


class TestComponent:
    async def test_lifecycle(self):
        with (
            patch("pykit_kafka.component.KafkaProducer") as MockProducer,
            patch("pykit_kafka.component.KafkaConsumer") as MockConsumer,
        ):
            mock_prod = AsyncMock()
            mock_cons = AsyncMock()
            MockProducer.return_value = mock_prod
            MockConsumer.return_value = mock_cons

            comp = KafkaComponent(KafkaConfig(name="test-kafka"))
            assert comp.name == "test-kafka"

            # Health before start
            h = await comp.health()
            assert h.status.value == "unhealthy"

            await comp.start()
            mock_prod.start.assert_awaited_once()
            mock_cons.start.assert_awaited_once()

            # Health after start
            h = await comp.health()
            assert h.status.value == "healthy"

            await comp.stop()
            mock_cons.stop.assert_awaited_once()
            mock_prod.stop.assert_awaited_once()

    async def test_properties(self):
        with (
            patch("pykit_kafka.component.KafkaProducer") as MockProducer,
            patch("pykit_kafka.component.KafkaConsumer") as MockConsumer,
        ):
            MockProducer.return_value = AsyncMock()
            MockConsumer.return_value = AsyncMock()

            comp = KafkaComponent(KafkaConfig())
            assert comp.producer is not None
            assert comp.consumer is not None

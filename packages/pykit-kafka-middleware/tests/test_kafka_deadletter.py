"""Tests for Kafka dead-letter producer."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock

from pykit_kafka_middleware.deadletter import DeadLetterProducer
from pykit_messaging.types import Message


def _make_msg(
    topic: str = "orders",
    value: bytes = b'{"id": 1}',
    headers: dict[str, str] | None = None,
) -> Message:
    return Message(
        key="k1",
        value=value,
        topic=topic,
        partition=0,
        offset=0,
        headers=headers or {},
    )


class TestDeadLetterProducer:
    async def test_sends_to_dlq_topic(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        msg = _make_msg(topic="orders")
        await dlq.send(msg, RuntimeError("processing failed"))

        mock_producer.send.assert_called_once()
        call_args = mock_producer.send.call_args
        assert call_args[0][0] == "orders.dlq"
        assert call_args[1]["key"] == "k1"

        envelope = json.loads(call_args[1]["value"])
        assert envelope["original_topic"] == "orders"
        assert envelope["error"] == "processing failed"
        assert envelope["retry_count"] == 0

    async def test_custom_suffix(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer, suffix=".dead")

        await dlq.send(_make_msg(topic="events"), RuntimeError("err"))

        call_args = mock_producer.send.call_args
        assert call_args[0][0] == "events.dead"

    async def test_reads_retry_count_from_headers(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        msg = _make_msg(headers={"x-retry-count": "3"})
        await dlq.send(msg, RuntimeError("err"))

        envelope = json.loads(mock_producer.send.call_args[1]["value"])
        assert envelope["retry_count"] == 3

    async def test_preserves_original_headers(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        msg = _make_msg(headers={"x-retry-count": "1", "trace-id": "abc"})
        await dlq.send(msg, RuntimeError("err"))

        envelope = json.loads(mock_producer.send.call_args[1]["value"])
        assert envelope["headers"]["trace-id"] == "abc"

    async def test_default_key_when_none(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        msg = _make_msg()
        msg.key = None
        await dlq.send(msg, RuntimeError("err"))

        call_args = mock_producer.send.call_args
        assert call_args[1]["key"] == "dlq"

    async def test_envelope_has_timestamp(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        await dlq.send(_make_msg(), RuntimeError("err"))

        envelope = json.loads(mock_producer.send.call_args[1]["value"])
        assert "timestamp" in envelope
        assert len(envelope["timestamp"]) > 0

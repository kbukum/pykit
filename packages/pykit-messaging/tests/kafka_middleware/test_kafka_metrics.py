"""Tests for Kafka metrics middleware."""

from __future__ import annotations

import pytest
from prometheus_client import REGISTRY

from pykit_messaging.kafka.middleware.metrics import InstrumentHandler
from pykit_messaging.types import Message


def _make_msg(topic: str = "test-topic") -> Message:
    return Message(key="k1", value=b"data", topic=topic, partition=0, offset=0, headers={})


def _get_sample_value(name: str, labels: dict[str, str]) -> float | None:
    """Read a metric sample value from the default Prometheus registry."""
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name == name and all(sample.labels.get(k) == v for k, v in labels.items()):
                return sample.value
    return None


class TestInstrumentHandler:
    async def test_records_messages_total(self) -> None:
        calls = 0

        async def handler(msg: Message) -> None:
            nonlocal calls
            calls += 1

        topic, group = "metrics-test-topic", "metrics-test-group"
        wrapped = InstrumentHandler(topic, group, handler)
        await wrapped(_make_msg())

        assert calls == 1
        val = _get_sample_value(
            "kafka_consumer_messages_total",
            {"topic": topic, "group": group},
        )
        assert val is not None and val >= 1.0

    async def test_records_errors_total(self) -> None:
        async def handler(msg: Message) -> None:
            raise RuntimeError("fail")

        topic, group = "err-test-topic", "err-test-group"
        wrapped = InstrumentHandler(topic, group, handler)

        with pytest.raises(RuntimeError):
            await wrapped(_make_msg())

        val = _get_sample_value(
            "kafka_consumer_errors_total",
            {"topic": topic, "group": group},
        )
        assert val is not None and val >= 1.0

    async def test_records_duration(self) -> None:
        async def handler(msg: Message) -> None:
            pass

        topic, group = "dur-test-topic", "dur-test-group"
        wrapped = InstrumentHandler(topic, group, handler)
        await wrapped(_make_msg())

        val = _get_sample_value(
            "kafka_consumer_processing_duration_seconds_count",
            {"topic": topic, "group": group},
        )
        assert val is not None and val >= 1.0

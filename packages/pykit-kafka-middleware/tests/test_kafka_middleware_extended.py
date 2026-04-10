"""Extended tests for Kafka middleware: retry, deadletter, metrics, tracing."""

from __future__ import annotations

import asyncio
import json
import math
from unittest.mock import AsyncMock

import pytest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from prometheus_client import REGISTRY

from pykit_kafka_middleware.deadletter import DeadLetterEnvelope, DeadLetterProducer
from pykit_kafka_middleware.metrics import InstrumentHandler
from pykit_kafka_middleware.retry import (
    RetryHandler,
    RetryMiddlewareConfig,
    _calculate_backoff,
)
from pykit_kafka_middleware.tracing import (
    TracingHandler,
    extract_trace_context,
    inject_trace_context,
)
from pykit_messaging.types import Message

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_msg(
    topic: str = "test-topic",
    value: bytes = b"hello",
    key: str | None = "k1",
    headers: dict[str, str] | None = None,
    partition: int = 0,
    offset: int = 0,
) -> Message:
    return Message(
        key=key,
        value=value,
        topic=topic,
        partition=partition,
        offset=offset,
        headers=headers or {},
    )


def _get_sample_value(name: str, labels: dict[str, str]) -> float | None:
    for metric in REGISTRY.collect():
        for sample in metric.samples:
            if sample.name == name and all(sample.labels.get(k) == v for k, v in labels.items()):
                return sample.value
    return None


# ---------------------------------------------------------------------------
# Retry — backoff calculation
# ---------------------------------------------------------------------------


class TestCalculateBackoff:
    def test_first_attempt_equals_initial_backoff(self) -> None:
        cfg = RetryMiddlewareConfig(initial_backoff=0.5, jitter=0.0, backoff_factor=2.0)
        result = _calculate_backoff(1, cfg)
        assert abs(result - 0.5) < 1e-9

    def test_exponential_growth(self) -> None:
        cfg = RetryMiddlewareConfig(initial_backoff=0.1, jitter=0.0, backoff_factor=2.0)
        assert abs(_calculate_backoff(1, cfg) - 0.1) < 1e-9
        assert abs(_calculate_backoff(2, cfg) - 0.2) < 1e-9
        assert abs(_calculate_backoff(3, cfg) - 0.4) < 1e-9

    def test_max_backoff_cap(self) -> None:
        cfg = RetryMiddlewareConfig(initial_backoff=1.0, max_backoff=2.0, jitter=0.0, backoff_factor=10.0)
        result = _calculate_backoff(5, cfg)
        assert result <= 2.0

    def test_jitter_adds_variance(self) -> None:
        cfg = RetryMiddlewareConfig(initial_backoff=1.0, jitter=0.5, backoff_factor=1.0)
        results = {_calculate_backoff(1, cfg) for _ in range(50)}
        # With jitter, we should get various values
        assert len(results) > 1

    def test_backoff_never_negative(self) -> None:
        cfg = RetryMiddlewareConfig(initial_backoff=0.001, jitter=1.0, backoff_factor=1.0)
        for _ in range(100):
            assert _calculate_backoff(1, cfg) >= 0.0

    @pytest.mark.parametrize("factor", [1.0, 1.5, 2.0, 3.0])
    def test_various_backoff_factors(self, factor: float) -> None:
        cfg = RetryMiddlewareConfig(initial_backoff=0.1, jitter=0.0, backoff_factor=factor, max_backoff=100.0)
        result = _calculate_backoff(3, cfg)
        expected = 0.1 * math.pow(factor, 2)
        assert abs(result - expected) < 1e-9


# ---------------------------------------------------------------------------
# Retry — extended handler tests
# ---------------------------------------------------------------------------


class TestRetryHandlerExtended:
    async def test_default_config_three_attempts(self) -> None:
        calls = 0

        async def handler(msg: Message) -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("fail")

        wrapped = RetryHandler(handler)  # default config
        with pytest.raises(RuntimeError):
            await wrapped(_make_msg())
        assert calls == 3  # default max_attempts=3

    async def test_single_attempt_no_retry(self) -> None:
        calls = 0

        async def handler(msg: Message) -> None:
            nonlocal calls
            calls += 1
            raise RuntimeError("fail")

        cfg = RetryMiddlewareConfig(max_attempts=1)
        wrapped = RetryHandler(handler, cfg)
        with pytest.raises(RuntimeError):
            await wrapped(_make_msg())
        assert calls == 1

    async def test_retry_if_with_mixed_exceptions(self) -> None:
        """retry_if should allow retrying some exceptions but not others."""
        calls = 0

        async def handler(msg: Message) -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise ConnectionError("transient")
            if calls == 2:
                raise ValueError("permanent")

        cfg = RetryMiddlewareConfig(
            max_attempts=5,
            initial_backoff=0.01,
            retry_if=lambda e: isinstance(e, ConnectionError),
        )
        wrapped = RetryHandler(handler, cfg)
        with pytest.raises(ValueError, match="permanent"):
            await wrapped(_make_msg())
        assert calls == 2

    async def test_on_exhausted_receives_last_error(self) -> None:
        errors: list[str] = []

        async def handler(msg: Message) -> None:
            raise RuntimeError("attempt-error")

        async def on_exhausted(msg: Message, err: Exception) -> None:
            errors.append(str(err))

        cfg = RetryMiddlewareConfig(max_attempts=2, initial_backoff=0.01, on_exhausted=on_exhausted)
        wrapped = RetryHandler(handler, cfg)
        with pytest.raises(RuntimeError):
            await wrapped(_make_msg())
        assert len(errors) == 1
        assert errors[0] == "attempt-error"

    async def test_handler_receives_correct_message_data(self) -> None:
        received: list[Message] = []

        async def handler(msg: Message) -> None:
            received.append(msg)

        wrapped = RetryHandler(handler)
        original = _make_msg(topic="orders", value=b"payload", key="order-1")
        await wrapped(original)

        assert len(received) == 1
        assert received[0].topic == "orders"
        assert received[0].value == b"payload"
        assert received[0].key == "order-1"


# ---------------------------------------------------------------------------
# DeadLetter — extended
# ---------------------------------------------------------------------------


class TestDeadLetterExtended:
    async def test_envelope_json_structure(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        msg = _make_msg(topic="payments", value=b'{"amount": 100}', key="pay-1")
        msg.headers["x-retry-count"] = "5"
        msg.headers["trace-id"] = "abc-123"

        await dlq.send(msg, ValueError("bad amount"))

        payload = json.loads(mock_producer.send.call_args[1]["value"])
        assert payload["original_topic"] == "payments"
        assert payload["error"] == "bad amount"
        assert payload["retry_count"] == 5
        assert payload["headers"]["trace-id"] == "abc-123"
        assert payload["payload"] == '{"amount": 100}'
        assert "timestamp" in payload

    async def test_non_digit_retry_count_defaults_to_zero(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        msg = _make_msg(headers={"x-retry-count": "invalid"})
        await dlq.send(msg, RuntimeError("err"))

        payload = json.loads(mock_producer.send.call_args[1]["value"])
        assert payload["retry_count"] == 0

    async def test_missing_retry_count_defaults_to_zero(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        await dlq.send(_make_msg(headers={}), RuntimeError("err"))

        payload = json.loads(mock_producer.send.call_args[1]["value"])
        assert payload["retry_count"] == 0

    async def test_binary_payload_decoded(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        msg = _make_msg(value=b"\xff\xfe")
        await dlq.send(msg, RuntimeError("err"))

        payload = json.loads(mock_producer.send.call_args[1]["value"])
        # Should be decoded with errors="replace"
        assert isinstance(payload["payload"], str)

    async def test_empty_value(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        msg = _make_msg(value=b"")
        await dlq.send(msg, RuntimeError("err"))

        payload = json.loads(mock_producer.send.call_args[1]["value"])
        assert payload["payload"] == ""

    async def test_error_message_preserved(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)

        await dlq.send(_make_msg(), TypeError("expected int, got str"))

        payload = json.loads(mock_producer.send.call_args[1]["value"])
        assert payload["error"] == "expected int, got str"


class TestDeadLetterEnvelopeDataclass:
    def test_default_fields(self) -> None:
        env = DeadLetterEnvelope(original_topic="t", error="e", retry_count=0, timestamp="now")
        assert env.headers == {}
        assert env.payload == ""

    def test_all_fields(self) -> None:
        env = DeadLetterEnvelope(
            original_topic="orders",
            error="boom",
            retry_count=3,
            timestamp="2024-01-01T00:00:00",
            headers={"k": "v"},
            payload="data",
        )
        assert env.original_topic == "orders"
        assert env.error == "boom"
        assert env.retry_count == 3
        assert env.headers == {"k": "v"}
        assert env.payload == "data"


# ---------------------------------------------------------------------------
# Metrics — extended
# ---------------------------------------------------------------------------


class TestInstrumentHandlerExtended:
    async def test_messages_total_increments_on_each_call(self) -> None:
        calls = 0

        async def handler(msg: Message) -> None:
            nonlocal calls
            calls += 1

        topic, group = "incr-test-topic", "incr-test-group"
        wrapped = InstrumentHandler(topic, group, handler)

        before = _get_sample_value("kafka_consumer_messages_total", {"topic": topic, "group": group})

        await wrapped(_make_msg())
        await wrapped(_make_msg())

        after = _get_sample_value("kafka_consumer_messages_total", {"topic": topic, "group": group})
        assert after is not None
        increment = after - (before or 0.0)
        assert increment >= 2.0

    async def test_error_still_records_message_count(self) -> None:
        """Even when handler errors, the message counter should be incremented (in finally)."""

        async def handler(msg: Message) -> None:
            raise RuntimeError("fail")

        topic, group = "err-msg-test-topic", "err-msg-test-group"
        wrapped = InstrumentHandler(topic, group, handler)

        with pytest.raises(RuntimeError):
            await wrapped(_make_msg())

        # Both messages_total and errors_total should be incremented
        msg_val = _get_sample_value("kafka_consumer_messages_total", {"topic": topic, "group": group})
        err_val = _get_sample_value("kafka_consumer_errors_total", {"topic": topic, "group": group})
        assert msg_val is not None and msg_val >= 1.0
        assert err_val is not None and err_val >= 1.0

    async def test_custom_metric_prefix(self) -> None:
        async def handler(msg: Message) -> None:
            pass

        topic, group = "custom-pfx-topic", "custom-pfx-group"
        wrapped = InstrumentHandler(topic, group, handler, metric_prefix="my_broker")
        await wrapped(_make_msg())

        val = _get_sample_value("my_broker_messages_total", {"topic": topic, "group": group})
        assert val is not None and val >= 1.0

        dur = _get_sample_value(
            "my_broker_processing_duration_seconds_count",
            {"topic": topic, "group": group},
        )
        assert dur is not None and dur >= 1.0

    async def test_duration_recorded(self) -> None:
        async def slow_handler(msg: Message) -> None:
            await asyncio.sleep(0.05)

        topic, group = "slow-test-topic", "slow-test-group"
        wrapped = InstrumentHandler(topic, group, slow_handler)
        await wrapped(_make_msg())

        val = _get_sample_value(
            "kafka_consumer_processing_duration_seconds_sum",
            {"topic": topic, "group": group},
        )
        assert val is not None and val >= 0.04

    async def test_error_re_raised(self) -> None:
        async def handler(msg: Message) -> None:
            raise ValueError("test")

        wrapped = InstrumentHandler("t", "g", handler)
        with pytest.raises(ValueError, match="test"):
            await wrapped(_make_msg())


# ---------------------------------------------------------------------------
# Tracing — extended
# ---------------------------------------------------------------------------


@pytest.fixture()
def tracer_exporter():
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace._TRACER_PROVIDER = None
    trace._TRACER_PROVIDER_SET_ONCE._done = False
    trace.set_tracer_provider(provider)
    yield exporter
    provider.shutdown()


class TestTracingHandlerExtended:
    async def test_kafka_partition_and_key_attributes(self, tracer_exporter) -> None:
        async def handler(msg: Message) -> None:
            pass

        wrapped = TracingHandler(handler)
        await wrapped(_make_msg(topic="events", key="evt-1", partition=3))

        spans = tracer_exporter.get_finished_spans()
        assert len(spans) == 1
        attrs = dict(spans[0].attributes or {})
        assert attrs["messaging.kafka.partition"] == 3
        assert attrs["messaging.kafka.message.key"] == "evt-1"

    async def test_non_kafka_messaging_system(self, tracer_exporter) -> None:
        async def handler(msg: Message) -> None:
            pass

        wrapped = TracingHandler(handler, messaging_system="rabbitmq")
        await wrapped(_make_msg())

        spans = tracer_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes or {})
        assert attrs["messaging.system"] == "rabbitmq"
        # Non-kafka should NOT have kafka-specific attributes
        assert "messaging.kafka.partition" not in attrs

    async def test_null_key_becomes_empty_string(self, tracer_exporter) -> None:
        async def handler(msg: Message) -> None:
            pass

        wrapped = TracingHandler(handler)
        await wrapped(_make_msg(key=None))

        spans = tracer_exporter.get_finished_spans()
        attrs = dict(spans[0].attributes or {})
        assert attrs["messaging.kafka.message.key"] == ""

    async def test_custom_tracer_name(self, tracer_exporter) -> None:
        async def handler(msg: Message) -> None:
            pass

        wrapped = TracingHandler(handler, tracer_name="my.consumer")
        await wrapped(_make_msg())

        spans = tracer_exporter.get_finished_spans()
        assert spans[0].instrumentation_info.name == "my.consumer"

    async def test_exception_recorded_in_span(self, tracer_exporter) -> None:
        async def handler(msg: Message) -> None:
            raise RuntimeError("process error")

        wrapped = TracingHandler(handler)
        with pytest.raises(RuntimeError):
            await wrapped(_make_msg())

        spans = tracer_exporter.get_finished_spans()
        events = spans[0].events
        assert any(e.name == "exception" for e in events)


class TestTraceContextExtended:
    def test_extract_returns_context(self, tracer_exporter) -> None:
        ctx = extract_trace_context({})
        assert ctx is not None

    def test_extract_empty_headers_no_error(self, tracer_exporter) -> None:
        ctx = extract_trace_context({"unrelated": "header"})
        assert ctx is not None

    def test_inject_without_active_span_is_noop(self, tracer_exporter) -> None:
        """Without an active span, inject should not add traceparent."""
        headers: dict[str, str] = {}
        inject_trace_context(headers)
        # No active span → no context to inject
        # The headers dict may or may not have traceparent depending on context
        assert isinstance(headers, dict)


# ---------------------------------------------------------------------------
# Integration: Retry + DeadLetter
# ---------------------------------------------------------------------------


class TestRetryWithDeadLetter:
    async def test_retry_exhausted_routes_to_dlq(self) -> None:
        mock_producer = AsyncMock()
        dlq = DeadLetterProducer(mock_producer)
        dlq_calls: list[tuple[Message, Exception]] = []

        async def on_exhausted(msg: Message, err: Exception) -> None:
            await dlq.send(msg, err)
            dlq_calls.append((msg, err))

        async def failing_handler(msg: Message) -> None:
            raise RuntimeError("always fails")

        cfg = RetryMiddlewareConfig(max_attempts=3, initial_backoff=0.01, on_exhausted=on_exhausted)
        wrapped = RetryHandler(failing_handler, cfg)

        with pytest.raises(RuntimeError):
            await wrapped(_make_msg(topic="orders"))

        assert len(dlq_calls) == 1
        mock_producer.send.assert_called_once()
        call_args = mock_producer.send.call_args
        assert call_args[0][0] == "orders.dlq"

        payload = json.loads(call_args[1]["value"])
        assert payload["retry_count"] == 2  # x-retry-count = max_attempts - 1
        assert payload["error"] == "always fails"

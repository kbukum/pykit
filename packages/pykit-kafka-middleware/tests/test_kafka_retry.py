"""Tests for Kafka retry middleware."""

from __future__ import annotations

import pytest

from pykit_kafka_middleware.retry import RetryHandler, RetryMiddlewareConfig
from pykit_messaging.types import Message


def _make_msg(topic: str = "test-topic", value: bytes = b"hello") -> Message:
    return Message(key="k1", value=value, topic=topic, partition=0, offset=0, headers={})


class TestRetryHandler:
    async def test_success_no_retry(self) -> None:
        calls = 0

        async def handler(msg: Message) -> None:
            nonlocal calls
            calls += 1

        wrapped = RetryHandler(handler, RetryMiddlewareConfig(max_attempts=3))
        await wrapped(_make_msg())
        assert calls == 1

    async def test_retries_then_succeeds(self) -> None:
        calls = 0

        async def handler(msg: Message) -> None:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise RuntimeError("transient")

        cfg = RetryMiddlewareConfig(max_attempts=3, initial_backoff=0.01)
        wrapped = RetryHandler(handler, cfg)
        await wrapped(_make_msg())
        assert calls == 3

    async def test_exhausted_raises(self) -> None:
        async def handler(msg: Message) -> None:
            raise RuntimeError("always fails")

        cfg = RetryMiddlewareConfig(max_attempts=2, initial_backoff=0.01)
        wrapped = RetryHandler(handler, cfg)

        with pytest.raises(RuntimeError, match="always fails"):
            await wrapped(_make_msg())

    async def test_on_exhausted_callback(self) -> None:
        exhausted_calls: list[tuple[str, str]] = []

        async def handler(msg: Message) -> None:
            raise RuntimeError("boom")

        async def on_exhausted(msg: Message, err: Exception) -> None:
            exhausted_calls.append((msg.topic, str(err)))

        cfg = RetryMiddlewareConfig(
            max_attempts=2,
            initial_backoff=0.01,
            on_exhausted=on_exhausted,
        )
        wrapped = RetryHandler(handler, cfg)

        with pytest.raises(RuntimeError):
            await wrapped(_make_msg(topic="orders"))

        assert len(exhausted_calls) == 1
        assert exhausted_calls[0][0] == "orders"
        assert "boom" in exhausted_calls[0][1]

    async def test_retry_count_header_updated(self) -> None:
        seen_headers: list[dict[str, str]] = []

        async def handler(msg: Message) -> None:
            seen_headers.append(dict(msg.headers))
            if len(seen_headers) < 3:
                raise RuntimeError("retry me")

        cfg = RetryMiddlewareConfig(max_attempts=3, initial_backoff=0.01)
        wrapped = RetryHandler(handler, cfg)
        await wrapped(_make_msg())

        assert len(seen_headers) == 3
        assert "x-retry-count" not in seen_headers[0]
        assert seen_headers[1]["x-retry-count"] == "1"
        assert seen_headers[2]["x-retry-count"] == "2"

    async def test_retry_if_skips_non_retryable(self) -> None:
        calls = 0

        async def handler(msg: Message) -> None:
            nonlocal calls
            calls += 1
            raise ValueError("permanent")

        cfg = RetryMiddlewareConfig(
            max_attempts=5,
            initial_backoff=0.01,
            retry_if=lambda e: not isinstance(e, ValueError),
        )
        wrapped = RetryHandler(handler, cfg)

        with pytest.raises(ValueError):
            await wrapped(_make_msg())

        assert calls == 1

    async def test_does_not_mutate_original_headers(self) -> None:
        original_headers = {"existing": "value"}
        msg = _make_msg()
        msg.headers = original_headers

        calls = 0

        async def handler(m: Message) -> None:
            nonlocal calls
            calls += 1
            if calls < 2:
                raise RuntimeError("retry")

        cfg = RetryMiddlewareConfig(max_attempts=3, initial_backoff=0.01)
        wrapped = RetryHandler(handler, cfg)
        await wrapped(msg)

        assert "x-retry-count" not in original_headers

"""Tests for circuit breaker middleware."""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest

from pykit_messaging.handler import FuncHandler, MessageHandlerProtocol
from pykit_messaging.middleware.circuit_breaker import (
    CircuitBreakerConfig,
    CircuitBreakerHandler,
    CircuitOpenError,
    CircuitState,
    circuit_breaker,
)
from pykit_messaging.types import Message


def _make_msg(topic: str = "test") -> Message:
    return Message(key=None, value=b"payload", topic=topic, partition=0, offset=0)


def _ok_handler() -> FuncHandler:
    async def _handle(msg: Message) -> None:
        pass

    return FuncHandler(_handle)


def _failing_handler(error: Exception | None = None) -> FuncHandler:
    async def _handle(msg: Message) -> None:
        raise error or RuntimeError("downstream error")

    return FuncHandler(_handle)


class TestCircuitBreakerHandler:
    async def test_closed_state_passes_through(self) -> None:
        received: list[Message] = []

        async def _handle(msg: Message) -> None:
            received.append(msg)

        cb = CircuitBreakerHandler(FuncHandler(_handle))

        msg = _make_msg()
        await cb.handle(msg)

        assert len(received) == 1
        assert cb.state == CircuitState.CLOSED

    async def test_opens_after_threshold_failures(self) -> None:
        config = CircuitBreakerConfig(threshold=3, timeout=30.0)
        cb = CircuitBreakerHandler(_failing_handler(), config)

        for _ in range(3):
            with pytest.raises(RuntimeError, match="downstream error"):
                await cb.handle(_make_msg())

        assert cb.state == CircuitState.OPEN

    async def test_open_rejects_immediately(self) -> None:
        config = CircuitBreakerConfig(threshold=2, timeout=30.0)
        cb = CircuitBreakerHandler(_failing_handler(), config)

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.handle(_make_msg())

        assert cb.state == CircuitState.OPEN

        # Now it should reject without calling inner
        with pytest.raises(CircuitOpenError):
            await cb.handle(_make_msg())

    async def test_half_open_after_timeout(self) -> None:
        config = CircuitBreakerConfig(threshold=2, timeout=1.0, half_open_max=1)
        cb = CircuitBreakerHandler(_failing_handler(), config)

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.handle(_make_msg())

        assert cb.state == CircuitState.OPEN

        # Simulate timeout
        base_time = time.monotonic()
        with patch("pykit_resilience.circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = base_time + 2.0
            assert cb.state == CircuitState.HALF_OPEN

    async def test_half_open_success_closes_circuit(self) -> None:
        call_count = 0
        threshold = 2

        async def _handle(msg: Message) -> None:
            nonlocal call_count
            call_count += 1
            if call_count <= threshold:
                raise RuntimeError("fail")

        config = CircuitBreakerConfig(threshold=threshold, timeout=1.0, half_open_max=1)
        cb = CircuitBreakerHandler(FuncHandler(_handle), config)

        # Trip the circuit
        for _ in range(threshold):
            with pytest.raises(RuntimeError):
                await cb.handle(_make_msg())

        # Simulate timeout elapsed by patching time
        base_time = time.monotonic()
        with patch("pykit_resilience.circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = base_time + 2.0
            assert cb.state == CircuitState.HALF_OPEN

            # Half-open: next call should succeed and close circuit
            await cb.handle(_make_msg())
            assert cb.state == CircuitState.CLOSED

    async def test_half_open_failure_reopens_circuit(self) -> None:
        config = CircuitBreakerConfig(threshold=2, timeout=1.0, half_open_max=1)
        cb = CircuitBreakerHandler(_failing_handler(), config)

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.handle(_make_msg())

        # Simulate timeout elapsed to transition to half-open
        base_time = time.monotonic()
        with patch("pykit_resilience.circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = base_time + 2.0
            assert cb.state == CircuitState.HALF_OPEN

            # Fail in half-open → reopens
            with pytest.raises(RuntimeError):
                await cb.handle(_make_msg())

            assert cb.state == CircuitState.OPEN

    async def test_half_open_max_probes(self) -> None:
        config = CircuitBreakerConfig(threshold=2, timeout=1.0, half_open_max=2)

        call_count = 0

        async def _handle(msg: Message) -> None:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("fail")

        cb = CircuitBreakerHandler(FuncHandler(_handle), config)

        # Trip the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.handle(_make_msg())

        assert cb.state == CircuitState.OPEN

        # Simulate timeout to transition to half-open
        base_time = time.monotonic()
        with patch("pykit_resilience.circuit_breaker.time") as mock_time:
            mock_time.monotonic.return_value = base_time + 2.0

            # Two probes should be allowed in half-open
            await cb.handle(_make_msg())
            await cb.handle(_make_msg())

            assert call_count == 4
            assert cb.state == CircuitState.CLOSED

    async def test_success_resets_failure_count(self) -> None:
        call_count = 0

        async def _handle(msg: Message) -> None:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("fail")

        config = CircuitBreakerConfig(threshold=5, timeout=30.0)
        cb = CircuitBreakerHandler(FuncHandler(_handle), config)

        # 2 failures
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.handle(_make_msg())
        assert cb.failures == 2

        # 1 success should reset failure count
        await cb.handle(_make_msg())
        assert cb.failures == 0
        assert cb.state == CircuitState.CLOSED

    async def test_circuit_breaker_middleware_factory(self) -> None:
        received: list[Message] = []

        async def _handle(msg: Message) -> None:
            received.append(msg)

        inner = FuncHandler(_handle)
        middleware = circuit_breaker()
        wrapped = middleware(inner)

        await wrapped.handle(_make_msg())
        assert len(received) == 1

    async def test_circuit_breaker_satisfies_protocol(self) -> None:
        cb = CircuitBreakerHandler(_ok_handler())
        assert isinstance(cb, MessageHandlerProtocol)

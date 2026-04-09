"""Tests for retry and metrics middleware."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest

from pykit_schema import ValidationResult
from pykit_tool.context import Context
from pykit_tool.definition import Definition
from pykit_tool.middleware_retry_metrics import (
    InMemoryMetrics,
    RetryConfig,
    with_metrics,
    with_retry,
)
from pykit_tool.result import Result, text_result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeTool:
    """Minimal Callable for testing middleware."""

    def __init__(self, name: str = "fake", handler: Any = None) -> None:
        self._definition = Definition(name=name, description="fake tool")
        self._handler = handler

    @property
    def definition(self) -> Definition:
        return self._definition

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        return ValidationResult(valid=True, errors=[])

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        if self._handler:
            return await self._handler(ctx, input_data)
        return text_result("ok")


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


class TestWithRetry:
    """Tests for retry middleware."""

    @pytest.mark.asyncio
    async def test_no_retry_on_success(self) -> None:
        call_count = 0

        async def handler(_ctx: Context, _data: dict[str, Any]) -> Result:
            nonlocal call_count
            call_count += 1
            return text_result("success")

        tool = _FakeTool(handler=handler)
        wrapped = with_retry(RetryConfig(max_attempts=3, base_delay=0.01))(tool)
        result = await wrapped.call(Context(), {})
        assert result.content == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_failure_then_succeeds(self) -> None:
        call_count = 0

        async def handler(_ctx: Context, _data: dict[str, Any]) -> Result:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("transient error")
            return text_result("recovered")

        tool = _FakeTool(handler=handler)
        wrapped = with_retry(RetryConfig(max_attempts=3, base_delay=0.01))(tool)
        result = await wrapped.call(Context(), {})
        assert result.content == "recovered"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_attempts(self) -> None:
        async def handler(_ctx: Context, _data: dict[str, Any]) -> Result:
            raise RuntimeError("permanent error")

        tool = _FakeTool(handler=handler)
        wrapped = with_retry(RetryConfig(max_attempts=2, base_delay=0.01))(tool)
        with pytest.raises(RuntimeError, match="permanent error"):
            await wrapped.call(Context(), {})

    @pytest.mark.asyncio
    async def test_should_retry_predicate_false(self) -> None:
        call_count = 0

        async def handler(_ctx: Context, _data: dict[str, Any]) -> Result:
            nonlocal call_count
            call_count += 1
            raise ValueError("non-retryable")

        tool = _FakeTool(handler=handler)
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.01,
            should_retry=lambda exc: not isinstance(exc, ValueError),
        )
        wrapped = with_retry(config)(tool)
        with pytest.raises(ValueError, match="non-retryable"):
            await wrapped.call(Context(), {})
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_default_config(self) -> None:
        async def handler(_ctx: Context, _data: dict[str, Any]) -> Result:
            return text_result("ok")

        tool = _FakeTool(handler=handler)
        wrapped = with_retry()(tool)
        result = await wrapped.call(Context(), {})
        assert result.content == "ok"

    def test_definition_passthrough(self) -> None:
        tool = _FakeTool(name="my_tool")
        wrapped = with_retry(RetryConfig(base_delay=0.01))(tool)
        assert wrapped.definition.name == "my_tool"

    def test_validate_passthrough(self) -> None:
        tool = _FakeTool()
        wrapped = with_retry(RetryConfig(base_delay=0.01))(tool)
        vr = wrapped.validate({"key": "value"})
        assert vr.valid


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


class TestInMemoryMetrics:
    """Tests for InMemoryMetrics collector."""

    def test_record_success(self) -> None:
        m = InMemoryMetrics()
        m.record_call("search", 0.5, None)
        assert m.calls["search"] == 1
        assert m.errors.get("search", 0) == 0
        assert m.total_duration["search"] == pytest.approx(0.5)

    def test_record_error(self) -> None:
        m = InMemoryMetrics()
        m.record_call("search", 0.1, RuntimeError("fail"))
        assert m.calls["search"] == 1
        assert m.errors["search"] == 1

    def test_multiple_calls(self) -> None:
        m = InMemoryMetrics()
        m.record_call("search", 0.5, None)
        m.record_call("search", 0.3, None)
        m.record_call("search", 0.2, RuntimeError("err"))
        assert m.calls["search"] == 3
        assert m.errors["search"] == 1
        assert m.total_duration["search"] == pytest.approx(1.0)

    def test_multiple_tools(self) -> None:
        m = InMemoryMetrics()
        m.record_call("search", 0.5, None)
        m.record_call("read", 0.1, None)
        assert m.calls["search"] == 1
        assert m.calls["read"] == 1


class TestWithMetrics:
    """Tests for metrics middleware."""

    @pytest.mark.asyncio
    async def test_records_successful_call(self) -> None:
        metrics = InMemoryMetrics()
        tool = _FakeTool(name="search")
        wrapped = with_metrics(metrics)(tool)
        await wrapped.call(Context(), {})
        assert metrics.calls["search"] == 1
        assert metrics.errors.get("search", 0) == 0
        assert metrics.total_duration["search"] > 0

    @pytest.mark.asyncio
    async def test_records_failed_call(self) -> None:
        async def handler(_ctx: Context, _data: dict[str, Any]) -> Result:
            raise RuntimeError("boom")

        metrics = InMemoryMetrics()
        tool = _FakeTool(name="search", handler=handler)
        wrapped = with_metrics(metrics)(tool)
        with pytest.raises(RuntimeError, match="boom"):
            await wrapped.call(Context(), {})
        assert metrics.calls["search"] == 1
        assert metrics.errors["search"] == 1

    @pytest.mark.asyncio
    async def test_records_duration(self) -> None:
        async def handler(_ctx: Context, _data: dict[str, Any]) -> Result:
            await asyncio.sleep(0.05)
            return text_result("ok")

        metrics = InMemoryMetrics()
        tool = _FakeTool(name="slow", handler=handler)
        wrapped = with_metrics(metrics)(tool)
        await wrapped.call(Context(), {})
        assert metrics.total_duration["slow"] >= 0.04

    def test_definition_passthrough(self) -> None:
        metrics = InMemoryMetrics()
        tool = _FakeTool(name="my_tool")
        wrapped = with_metrics(metrics)(tool)
        assert wrapped.definition.name == "my_tool"

    def test_validate_passthrough(self) -> None:
        metrics = InMemoryMetrics()
        tool = _FakeTool()
        wrapped = with_metrics(metrics)(tool)
        vr = wrapped.validate({})
        assert vr.valid


class TestMetricsCollectorProtocol:
    """Verify MetricsCollector protocol."""

    def test_in_memory_satisfies_protocol(self) -> None:
        from pykit_tool.middleware_retry_metrics import MetricsCollector

        m = InMemoryMetrics()
        assert isinstance(m, MetricsCollector)

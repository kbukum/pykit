"""Retry and metrics middleware for tool execution."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Callable as CallableFn
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from pykit_schema import ValidationResult
from pykit_tool.callable import Callable
from pykit_tool.context import Context
from pykit_tool.definition import Definition
from pykit_tool.middleware import Middleware
from pykit_tool.result import Result

# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------


@dataclass
class RetryConfig:
    """Configuration for retry middleware."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 30.0
    should_retry: CallableFn[[Exception], bool] | None = None


def with_retry(config: RetryConfig | None = None) -> Middleware:
    """Middleware that retries failed tool calls with exponential backoff and jitter.

    Args:
        config: Retry configuration. Uses defaults if not provided.

    Returns:
        A middleware that wraps a Callable with retry logic.
    """
    cfg = config or RetryConfig()

    def middleware(tool: Callable) -> Callable:
        return _RetryWrapper(tool, cfg)

    return middleware


class _RetryWrapper:
    """Wraps a tool with retry logic."""

    def __init__(self, inner: Callable, config: RetryConfig) -> None:
        self._inner = inner
        self._config = config

    @property
    def definition(self) -> Definition:
        return self._inner.definition

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        return self._inner.validate(input_data)

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        last_error: Exception | None = None
        for attempt in range(self._config.max_attempts):
            try:
                return await self._inner.call(ctx, input_data)
            except Exception as exc:
                last_error = exc
                if self._config.should_retry and not self._config.should_retry(exc):
                    raise
                if attempt + 1 >= self._config.max_attempts:
                    raise
                delay = min(
                    self._config.base_delay * (2**attempt),
                    self._config.max_delay,
                )
                jitter = random.uniform(0, delay * 0.5)
                await asyncio.sleep(delay + jitter)
        raise last_error  # type: ignore[misc]  # unreachable but satisfies type checker


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


@runtime_checkable
class MetricsCollector(Protocol):
    """Protocol for recording tool call metrics."""

    def record_call(self, tool_name: str, duration: float, error: Exception | None) -> None:
        """Record a single tool invocation.

        Args:
            tool_name: Name of the tool that was called.
            duration: Execution duration in seconds.
            error: The exception if the call failed, else None.
        """
        ...


@dataclass
class InMemoryMetrics:
    """Simple in-memory metrics collector for testing and development."""

    calls: dict[str, int] = field(default_factory=dict)
    errors: dict[str, int] = field(default_factory=dict)
    total_duration: dict[str, float] = field(default_factory=dict)

    def record_call(self, tool_name: str, duration: float, error: Exception | None) -> None:
        """Record a tool call metric."""
        self.calls[tool_name] = self.calls.get(tool_name, 0) + 1
        self.total_duration[tool_name] = self.total_duration.get(tool_name, 0.0) + duration
        if error is not None:
            self.errors[tool_name] = self.errors.get(tool_name, 0) + 1


def with_metrics(collector: MetricsCollector) -> Middleware:
    """Middleware that records call count, latency, and error count per tool.

    Args:
        collector: The metrics collector to record to.

    Returns:
        A middleware that wraps a Callable with metrics recording.
    """

    def middleware(tool: Callable) -> Callable:
        return _MetricsWrapper(tool, collector)

    return middleware


class _MetricsWrapper:
    """Wraps a tool with metrics recording."""

    def __init__(self, inner: Callable, collector: MetricsCollector) -> None:
        self._inner = inner
        self._collector = collector

    @property
    def definition(self) -> Definition:
        return self._inner.definition

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        return self._inner.validate(input_data)

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        name = self.definition.name
        start = time.monotonic()
        error: Exception | None = None
        try:
            result = await self._inner.call(ctx, input_data)
            return result
        except Exception as exc:
            error = exc
            raise
        finally:
            duration = time.monotonic() - start
            self._collector.record_call(name, duration, error)

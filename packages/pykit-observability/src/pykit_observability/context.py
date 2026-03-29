"""Operation context tying request metadata, spans, and metrics."""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from opentelemetry import trace


class OperationContext:
    """Ties request metadata, spans, and metrics for an operation."""

    def __init__(
        self,
        operation_name: str,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        self.operation_name = operation_name
        self.attributes = attributes or {}
        self._span: trace.Span | None = None
        self._start_time: float = 0.0

    @property
    def span(self) -> trace.Span:
        """Return the current span, or INVALID_SPAN if not inside context."""
        if self._span is not None:
            return self._span
        return trace.INVALID_SPAN

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the current span."""
        self.span.set_attribute(key, value)

    def record_error(self, error: BaseException) -> None:
        """Record an error on the current span."""
        self.span.set_status(trace.StatusCode.ERROR, str(error))
        self.span.record_exception(error)

    @property
    def elapsed(self) -> float:
        """Seconds since the context was entered."""
        if self._start_time == 0.0:
            return 0.0
        return time.monotonic() - self._start_time

    @asynccontextmanager
    async def __call__(self) -> AsyncIterator[OperationContext]:
        """Use as ``async with ctx(): ...``."""
        tracer = trace.get_tracer(self.operation_name)
        with tracer.start_as_current_span(
            self.operation_name,
            attributes=self.attributes,
        ) as span:
            self._span = span
            self._start_time = time.monotonic()
            try:
                yield self
            except BaseException as exc:
                self.record_error(exc)
                raise
            finally:
                self._span = None

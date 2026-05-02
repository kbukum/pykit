"""Transport-neutral span helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from enum import Enum

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.trace import StatusCode


class SpanKind(Enum):
    """Role a span plays in a distributed trace."""

    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


_SPAN_KIND_MAP = {
    SpanKind.INTERNAL: trace.SpanKind.INTERNAL,
    SpanKind.SERVER: trace.SpanKind.SERVER,
    SpanKind.CLIENT: trace.SpanKind.CLIENT,
    SpanKind.PRODUCER: trace.SpanKind.PRODUCER,
    SpanKind.CONSUMER: trace.SpanKind.CONSUMER,
}


class Span:
    """Small wrapper around the active tracing span."""

    def __init__(self, span: trace.Span) -> None:
        self._span = span

    def set_attribute(self, key: str, value: str | int | float | bool) -> None:
        """Set an attribute on the span."""
        self._span.set_attribute(key, value)

    def record_exception(self, exc: Exception) -> None:
        """Record an exception on the span."""
        self._span.record_exception(exc)

    def set_error(self, message: str) -> None:
        """Mark the span as failed."""
        self._span.set_status(StatusCode.ERROR, message)


@contextmanager
def start_span(
    tracer_name: str,
    span_name: str,
    *,
    context: otel_context.Context | None = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: dict[str, str | int | float | bool] | None = None,
) -> Iterator[Span]:
    """Start a span from a named tracer."""
    tracer = trace.get_tracer(tracer_name)
    with tracer.start_as_current_span(
        span_name,
        context=context,
        kind=_SPAN_KIND_MAP[kind],
        attributes=attributes,
    ) as span:
        yield Span(span)

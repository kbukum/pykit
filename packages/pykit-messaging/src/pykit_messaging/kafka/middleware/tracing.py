"""Distributed tracing middleware for message handlers."""

from __future__ import annotations

from collections.abc import Callable

from pykit_messaging.types import Message, MessageHandler
from pykit_observability import MappingCarrier, SpanKind, TraceContext, start_span
from pykit_observability import extract_trace_context as extract_observability_context
from pykit_observability import inject_trace_context as inject_observability_context


def inject_trace_context(headers: dict[str, str]) -> None:
    """Inject the current span's trace context into message headers."""
    inject_observability_context(MappingCarrier(headers))


def extract_trace_context(headers: dict[str, str]) -> TraceContext:
    """Extract trace context from message headers."""
    return extract_observability_context(MappingCarrier(headers))


def TracingHandler(
    handler: MessageHandler,
    *,
    tracer_name: str = "kafka.consumer",
    span_name_func: Callable[[Message], str] | None = None,
    messaging_system: str = "kafka",
) -> MessageHandler:
    """Wrap a MessageHandler with OpenTelemetry distributed tracing.

    Extracts W3C TraceContext from message headers, creates a consumer span,
    and annotates it with messaging-specific attributes.

    Parameters
    ----------
    tracer_name:
        OpenTelemetry tracer name. Defaults to ``"kafka.consumer"`` for
        backward compatibility.
    span_name_func:
        Optional callable that produces the span name from the message.
    messaging_system:
        Value for the ``messaging.system`` span attribute. Defaults to
        ``"kafka"``; pass a different value for non-Kafka brokers.
    """

    def _default_span_name(msg: Message) -> str:
        return f"{msg.topic} consume"

    name_func = span_name_func or _default_span_name

    async def wrapper(msg: Message) -> None:
        ctx = extract_trace_context(msg.headers)
        span_name = name_func(msg)

        attrs: dict[str, str | int] = {
            "messaging.system": messaging_system,
            "messaging.destination": msg.topic,
        }
        if messaging_system == "kafka":
            attrs["messaging.kafka.partition"] = msg.partition
            attrs["messaging.kafka.message.key"] = msg.key or ""

        with start_span(
            tracer_name,
            span_name,
            context=ctx,
            kind=SpanKind.CONSUMER,
            attributes=attrs,
        ) as span:
            try:
                await handler(msg)
            except Exception as exc:
                span.record_exception(exc)
                span.set_error(str(exc))
                raise

    return wrapper

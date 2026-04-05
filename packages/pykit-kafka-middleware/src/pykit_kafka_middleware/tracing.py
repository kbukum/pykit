"""Distributed tracing middleware for message handlers."""

from __future__ import annotations

from collections.abc import Callable

from opentelemetry import context as otel_context
from opentelemetry import trace
from opentelemetry.propagate import extract, inject
from opentelemetry.trace import StatusCode

from pykit_messaging.types import Message, MessageHandler


class _HeaderCarrier:
    """Adapts a ``dict[str, str]`` to the OpenTelemetry TextMap interface."""

    def __init__(self, headers: dict[str, str]) -> None:
        self._headers = headers

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._headers.get(key, default)

    def set(self, key: str, value: str) -> None:
        self._headers[key] = value

    def keys(self) -> list[str]:
        return list(self._headers)


def inject_trace_context(headers: dict[str, str]) -> None:
    """Inject the current span's trace context into message headers."""
    inject(carrier=_HeaderCarrier(headers))


def extract_trace_context(headers: dict[str, str]) -> otel_context.Context:
    """Extract trace context from message headers."""
    return extract(carrier=_HeaderCarrier(headers))


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
        tracer = trace.get_tracer(tracer_name)
        ctx = extract_trace_context(msg.headers)
        span_name = name_func(msg)

        attrs: dict[str, str | int] = {
            "messaging.system": messaging_system,
            "messaging.destination": msg.topic,
        }
        if messaging_system == "kafka":
            attrs["messaging.kafka.partition"] = msg.partition
            attrs["messaging.kafka.message.key"] = msg.key or ""

        with tracer.start_as_current_span(
            span_name,
            context=ctx,
            kind=trace.SpanKind.CONSUMER,
            attributes=attrs,
        ) as span:
            try:
                await handler(msg)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(StatusCode.ERROR, str(exc))
                raise

    return wrapper

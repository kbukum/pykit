"""Transport-neutral trace-context propagation helpers."""

from __future__ import annotations

from typing import Protocol

from opentelemetry import context as otel_context
from opentelemetry.propagate import extract, inject

TraceContext = otel_context.Context


class TextMapCarrier(Protocol):
    """Carrier protocol for text-map propagation."""

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return the value for key, or default."""

    def set(self, key: str, value: str) -> None:
        """Store value under key."""

    def keys(self) -> list[str]:
        """Return available carrier keys."""


class MappingCarrier:
    """Adapt ``dict[str, str]`` headers for trace propagation."""

    def __init__(self, headers: dict[str, str]) -> None:
        self._headers = headers

    def get(self, key: str, default: str | None = None) -> str | None:
        """Return the value for key, or default."""
        return self._headers.get(key, default)

    def set(self, key: str, value: str) -> None:
        """Store value under key."""
        self._headers[key] = value

    def keys(self) -> list[str]:
        """Return available carrier keys."""
        return list(self._headers)


def inject_trace_context(carrier: TextMapCarrier) -> None:
    """Inject the current trace context into carrier."""
    inject(carrier=carrier)


def extract_trace_context(carrier: TextMapCarrier) -> TraceContext:
    """Extract a trace context from carrier."""
    return extract(carrier=carrier)

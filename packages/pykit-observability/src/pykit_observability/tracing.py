"""OpenTelemetry tracing setup and helpers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    TraceIdRatioBased,
)

from pykit_observability.config import TracerConfig


def setup_tracing(config: TracerConfig) -> TracerProvider:
    """Configure and set the global OTel tracer provider."""
    resource = Resource.create({"service.name": config.service_name})

    if config.sample_rate >= 1.0:
        sampler = ALWAYS_ON
    elif config.sample_rate <= 0:
        sampler = ALWAYS_OFF
    else:
        sampler = TraceIdRatioBased(config.sample_rate)

    provider = TracerProvider(resource=resource, sampler=sampler)
    trace.set_tracer_provider(provider)
    return provider


def get_tracer(name: str) -> trace.Tracer:
    """Return a named tracer from the global provider."""
    return trace.get_tracer(name)


@asynccontextmanager
async def trace_operation(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> AsyncIterator[trace.Span]:
    """Async context manager that creates and manages a span."""
    tracer = trace.get_tracer(name)
    with tracer.start_as_current_span(name, attributes=attributes) as span:
        yield span

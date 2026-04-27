"""OpenTelemetry tracing setup and helpers."""

from __future__ import annotations

import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, cast

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.sampling import (
    ALWAYS_OFF,
    ALWAYS_ON,
    Sampler,
    TraceIdRatioBased,
)

from pykit_observability.config import TracerConfig

_setup_lock = threading.Lock()
_tracer_provider: Any = None


def _build_provider(config: TracerConfig) -> TracerProvider:
    resource = Resource.create({"service.name": config.service_name})

    sampler: Sampler
    if config.sample_rate >= 1.0:
        sampler = ALWAYS_ON
    elif config.sample_rate <= 0:
        sampler = ALWAYS_OFF
    else:
        sampler = TraceIdRatioBased(config.sample_rate)

    provider = TracerProvider(resource=resource, sampler=sampler)

    if not getattr(config, "otlp_endpoint", None) and not getattr(config, "exporter", None):
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))

    return provider


def setup_tracing(config: TracerConfig) -> TracerProvider:
    """Configure and set the global OTel tracer provider. Idempotent — safe to call multiple times."""
    global _tracer_provider
    with _setup_lock:
        if _tracer_provider is not None:
            return cast("TracerProvider", _tracer_provider)
        provider = _build_provider(config)
        trace.set_tracer_provider(provider)

        try:
            from opentelemetry.propagate import set_global_textmap
            from opentelemetry.propagators.b3 import B3MultiFormat
            from opentelemetry.propagators.composite import CompositePropagator
            from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

            set_global_textmap(
                CompositePropagator(
                    [
                        TraceContextTextMapPropagator(),
                        B3MultiFormat(),
                    ]
                )
            )
        except ImportError:
            from opentelemetry.propagate import set_global_textmap
            from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

            set_global_textmap(TraceContextTextMapPropagator())

        _tracer_provider = provider
        return provider


def reset_tracing() -> None:
    """Reset to NoOp provider. Intended for test teardown only."""
    global _tracer_provider
    with _setup_lock:
        trace.set_tracer_provider(trace.ProxyTracerProvider())
        _tracer_provider = None


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

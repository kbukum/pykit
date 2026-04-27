"""Benchmarks for the DI container resolve performance."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.benchmark


def test_container_resolve_simple(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark resolving a simple registered value."""
    try:
        from pykit_di import Container

        container = Container()
        obj = object()
        container.register_instance("service_key", obj)
        benchmark(lambda: container.resolve("service_key", type(obj)))
    except ImportError:
        pytest.skip("pykit-di not available")


def test_container_resolve_lazy(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark resolving a lazy-registered component."""
    try:
        from pykit_di import Container

        container = Container()
        container.register_lazy("counter", lambda: {"value": 0})
        benchmark(lambda: container.resolve("counter"))
    except ImportError:
        pytest.skip("pykit-di not available")

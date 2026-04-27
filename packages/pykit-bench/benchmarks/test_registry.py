"""Benchmarks for the Registry class."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.benchmark


def test_registry_get(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark registry lookup."""
    try:
        from pykit_util.registry import Registry

        reg: Registry[str, str] = Registry()
        reg.register_sync("key", "value")
        benchmark(lambda: reg.get("key"))
    except ImportError:
        pytest.skip("pykit-util.registry not available")


def test_registry_contains(benchmark: pytest.FixtureRequest) -> None:
    """Benchmark registry membership check."""
    try:
        from pykit_util.registry import Registry

        reg: Registry[str, int] = Registry()
        for i in range(100):
            reg.register_sync(f"key_{i}", i)
        benchmark(lambda: "key_50" in reg)
    except ImportError:
        pytest.skip("pykit-util.registry not available")

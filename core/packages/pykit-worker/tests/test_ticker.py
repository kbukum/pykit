"""Tests for TickerWorker."""

from __future__ import annotations

import asyncio

import pytest

from pykit_component import HealthStatus
from pykit_worker.ticker import TickerWorker


@pytest.mark.asyncio
async def test_runs_on_interval() -> None:
    count = 0

    async def handler() -> None:
        nonlocal count
        count += 1

    tw = TickerWorker("test", interval=0.02, handler=handler)
    await tw.start()
    await asyncio.sleep(0.07)
    await tw.stop()

    assert count >= 2, f"expected ≥2 ticks, got {count}"


@pytest.mark.asyncio
async def test_health_before_start() -> None:
    tw = TickerWorker("h", interval=1.0, handler=_noop)
    h = await tw.health()
    assert h.status == HealthStatus.UNHEALTHY


@pytest.mark.asyncio
async def test_health_after_start() -> None:
    tw = TickerWorker("h", interval=0.01, handler=_noop)
    await tw.start()
    await asyncio.sleep(0.03)
    h = await tw.health()
    assert h.status == HealthStatus.HEALTHY
    await tw.stop()


@pytest.mark.asyncio
async def test_health_degraded_on_error() -> None:
    async def boom() -> None:
        raise RuntimeError("boom")

    tw = TickerWorker("err", interval=0.01, handler=boom)
    await tw.start()
    await asyncio.sleep(0.03)
    h = await tw.health()
    assert h.status == HealthStatus.DEGRADED
    assert "boom" in h.message
    await tw.stop()


@pytest.mark.asyncio
async def test_stop_idempotent() -> None:
    tw = TickerWorker("idem", interval=1.0, handler=_noop)
    await tw.stop()  # before start
    await tw.start()
    await tw.stop()
    await tw.stop()  # double stop


def test_name() -> None:
    tw = TickerWorker("my-worker", interval=1.0, handler=_noop)
    assert tw.name == "my-worker"


@pytest.mark.asyncio
async def test_run_count() -> None:
    tw = TickerWorker("cnt", interval=0.01, handler=_noop)
    await tw.start()
    await asyncio.sleep(0.035)
    await tw.stop()
    assert tw.run_count >= 2


async def _noop() -> None:
    pass

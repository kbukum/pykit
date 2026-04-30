"""Tests for worker pool overflow and dispatch policies."""

from __future__ import annotations

import asyncio

import pytest

from pykit_worker import (
    DispatchStrategy,
    OverflowPolicy,
    PoolConfig,
    PoolOverflowError,
    TaskStatus,
    WorkerPool,
)


class TestOverflowPolicies:
    @pytest.mark.asyncio
    async def test_reject_overflow_raises(self) -> None:
        gate = asyncio.Event()
        pool = WorkerPool(
            PoolConfig(
                max_workers=1,
                max_pending_tasks=0,
                overflow_policy=OverflowPolicy.REJECT,
            )
        )

        async def block() -> None:
            await gate.wait()

        task = await pool.submit("first", block)
        await asyncio.sleep(0.01)

        with pytest.raises(PoolOverflowError):
            await pool.submit("second", block)

        gate.set()
        result = await pool.wait(task.id)
        assert result.status == TaskStatus.COMPLETED
        await pool.shutdown()

    @pytest.mark.asyncio
    async def test_drop_oldest_cancels_pending_task(self) -> None:
        gate = asyncio.Event()
        pool = WorkerPool(
            PoolConfig(
                max_workers=1,
                max_pending_tasks=1,
                overflow_policy=OverflowPolicy.DROP_OLDEST,
            )
        )

        async def block(value: int) -> int:
            if value == 1:
                await gate.wait()
            return value

        first = await pool.submit("first", block, 1)
        await asyncio.sleep(0.01)
        second = await pool.submit("second", block, 2)
        third = await pool.submit("third", block, 3)

        gate.set()

        second_result = await pool.wait(second.id)
        third_result = await pool.wait(third.id)
        first_result = await pool.wait(first.id)

        assert second_result.status == TaskStatus.CANCELLED
        assert third_result.status == TaskStatus.COMPLETED
        assert third_result.result == 3
        assert first_result.status == TaskStatus.COMPLETED
        await pool.shutdown()


class TestDispatchStrategies:
    @pytest.mark.asyncio
    async def test_round_robin_balances_slot_loads(self) -> None:
        gate = asyncio.Event()
        pool = WorkerPool(PoolConfig(max_workers=3, dispatch_strategy=DispatchStrategy.ROUND_ROBIN))

        async def block() -> None:
            await gate.wait()

        tasks = [await pool.submit(f"task-{index}", block) for index in range(3)]
        await asyncio.sleep(0.01)

        assert pool._slot_loads == [1, 1, 1]

        gate.set()
        await asyncio.gather(*(pool.wait(task.id) for task in tasks))
        await pool.shutdown()

    @pytest.mark.asyncio
    async def test_least_loaded_prefers_less_busy_slot(self) -> None:
        gate = asyncio.Event()
        pool = WorkerPool(PoolConfig(max_workers=2, dispatch_strategy=DispatchStrategy.LEAST_LOADED))

        async def block() -> None:
            await gate.wait()

        tasks = [await pool.submit(f"task-{index}", block) for index in range(3)]
        await asyncio.sleep(0.01)

        assert sorted(pool._slot_loads) == [1, 2]

        gate.set()
        await asyncio.gather(*(pool.wait(task.id) for task in tasks))
        await pool.shutdown()

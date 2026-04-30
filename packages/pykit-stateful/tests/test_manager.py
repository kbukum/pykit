"""Tests for manager multiplexing and TTL cleanup."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from pykit_stateful import Accumulator, AccumulatorConfig, Manager


async def _wait_until(predicate: Callable[[], bool], timeout: float = 0.3) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() >= deadline:
            raise AssertionError("condition not met before timeout")
        await asyncio.sleep(0.01)


class TestAccumulatorTTL:
    @pytest.mark.asyncio
    async def test_ttl_cleanup_clears_buffer(self) -> None:
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        accumulator = Accumulator(AccumulatorConfig(ttl=0.05), on_flush)
        assert accumulator._ttl_task is None
        await accumulator.push(1)
        assert accumulator._ttl_task is not None
        await _wait_until(lambda: accumulator.count == 0)
        assert flushed == []
        await accumulator.aclose()


class TestManager:
    @pytest.mark.asyncio
    async def test_get_or_create_reuses_accumulator(self) -> None:
        async def on_flush(_items: list[int]) -> None:
            pass

        manager = Manager(lambda _key: Accumulator(AccumulatorConfig(), on_flush), cleanup_interval=0)
        first = await manager.get_or_create("alpha")
        second = await manager.get_or_create("alpha")
        assert first is second
        await manager.close()

    @pytest.mark.asyncio
    async def test_push_and_flush_by_key(self) -> None:
        flushed: dict[str, list[list[int]]] = {"a": [], "b": []}

        def factory(key: str) -> Accumulator[int]:
            async def on_flush(items: list[int]) -> None:
                flushed[key].append(items)

            return Accumulator(AccumulatorConfig(), on_flush)

        manager = Manager(factory, cleanup_interval=0)
        await manager.push("a", 1)
        await manager.push("a", 2)
        await manager.push("b", 3)
        await manager.flush("a")
        await manager.flush("b")

        assert flushed["a"] == [[1, 2]]
        assert flushed["b"] == [[3]]
        await manager.close()

    @pytest.mark.asyncio
    async def test_cleanup_removes_expired_accumulators(self) -> None:
        async def on_flush(_items: list[int]) -> None:
            pass

        manager = Manager(
            lambda _key: Accumulator(AccumulatorConfig(ttl=0.05), on_flush),
            cleanup_interval=0.02,
        )
        await manager.push("session", 1)
        await _wait_until(lambda: manager._accumulators == {})
        await manager.close()

    @pytest.mark.asyncio
    async def test_delete_reports_presence(self) -> None:
        async def on_flush(_items: list[int]) -> None:
            pass

        manager = Manager(lambda _key: Accumulator(AccumulatorConfig(), on_flush), cleanup_interval=0)
        await manager.push("session", 1)
        deleted_session = await manager.delete("session")
        assert deleted_session is True
        deleted_missing = await manager.delete("missing")
        assert deleted_missing is False
        await manager.close()


def test_construct_outside_running_loop_does_not_start_task() -> None:
    async def on_flush(_items: list[int]) -> None:
        return None

    accumulator = Accumulator(AccumulatorConfig(ttl=0.05), on_flush)
    manager: Manager[str, int] = Manager(lambda _key: accumulator, cleanup_interval=0.01)

    assert accumulator._ttl_task is None
    assert manager._cleanup_task is None


@pytest.mark.asyncio
async def test_push_during_ttl_window_preserves_buffer() -> None:
    async def on_flush(_items: list[int]) -> None:
        return None

    accumulator = Accumulator(AccumulatorConfig(ttl=0.08), on_flush)
    await accumulator.push(1)
    await asyncio.sleep(0.04)
    await accumulator.push(2)
    await asyncio.sleep(0.05)
    assert accumulator.count == 2
    await _wait_until(lambda: accumulator.count == 0, timeout=0.3)
    await accumulator.aclose()


@pytest.mark.asyncio
async def test_manager_acquire_reuses_accumulator() -> None:
    async def on_flush(_items: list[int]) -> None:
        return None

    manager: Manager[str, int] = Manager(lambda _key: Accumulator(AccumulatorConfig(), on_flush), cleanup_interval=0)
    first = await manager.acquire("key")
    second = await manager.acquire("key")
    assert first is second
    await manager.aclose()


@pytest.mark.asyncio
async def test_aclose_is_idempotent_and_cancels_cleanup() -> None:
    async def on_flush(_items: list[int]) -> None:
        return None

    accumulator = Accumulator(AccumulatorConfig(ttl=0.2), on_flush)
    await accumulator.push(1)
    task = accumulator._ttl_task
    assert task is not None
    await accumulator.aclose()
    await accumulator.aclose()
    assert task.cancelled()

    manager: Manager[str, int] = Manager(lambda _key: Accumulator(AccumulatorConfig(), on_flush), cleanup_interval=0.2)
    await manager.get_or_create("key")
    cleanup_task = manager._cleanup_task
    assert cleanup_task is not None
    await manager.aclose()
    await manager.aclose()
    assert cleanup_task.cancelled()

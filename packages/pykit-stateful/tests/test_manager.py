# mypy: ignore-errors
"""Tests for manager multiplexing and TTL cleanup."""

from __future__ import annotations

import asyncio

import pytest

from pykit_stateful import Accumulator, AccumulatorConfig, Manager


async def _wait_until(predicate, timeout: float = 0.3) -> None:
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
        await accumulator.push(1)
        await _wait_until(lambda: accumulator.count == 0)
        assert flushed == []
        await accumulator.close()


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

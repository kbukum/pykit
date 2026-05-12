"""Tests for additional pipeline operators."""

from __future__ import annotations

import asyncio

import pytest

from pykit_pipeline import Pipeline, PipelineIterator, collect


class DelayedIterator(PipelineIterator[int]):
    """Iterator that yields values after configurable delays."""

    def __init__(self, items: list[int], delays: list[float]) -> None:
        self._items = items
        self._delays = delays
        self._index = 0

    async def next(self) -> int | None:
        if self._index >= len(self._items):
            return None
        await asyncio.sleep(self._delays[self._index])
        value = self._items[self._index]
        self._index += 1
        return value


class TestPipelineOperators:
    @pytest.mark.asyncio
    async def test_batch_groups_values(self) -> None:
        pipeline = Pipeline.from_list([1, 2, 3, 4, 5]).batch(2)
        assert await collect(pipeline) == [[1, 2], [3, 4], [5]]

    @pytest.mark.asyncio
    async def test_tumbling_window_groups_values(self) -> None:
        pipeline = Pipeline.from_list([1, 2, 3, 4, 5]).tumbling_window(3)
        assert await collect(pipeline) == [[1, 2, 3], [4, 5]]

    @pytest.mark.asyncio
    async def test_sliding_window_overlaps_values(self) -> None:
        pipeline = Pipeline.from_list([1, 2, 3, 4, 5]).sliding_window(3, step=2)
        assert await collect(pipeline) == [[1, 2, 3], [3, 4, 5]]

    @pytest.mark.asyncio
    async def test_parallel_applies_function_concurrently(self) -> None:
        current = 0
        high_water = 0
        lock = asyncio.Lock()

        async def work(value: int) -> int:
            nonlocal current, high_water
            async with lock:
                current += 1
                high_water = max(high_water, current)
            await asyncio.sleep(0.02)
            async with lock:
                current -= 1
            return value * 2

        results = await collect(Pipeline.from_list([1, 2, 3, 4]).parallel(2, work))
        assert sorted(results) == [2, 4, 6, 8]
        assert high_water <= 2

    @pytest.mark.asyncio
    async def test_merge_combines_pipelines(self) -> None:
        left = Pipeline.from_fn(lambda: DelayedIterator([1, 3], [0.0, 0.02]))
        right = Pipeline.from_fn(lambda: DelayedIterator([2, 4], [0.01, 0.0]))
        results = await collect(left.merge(right))
        assert sorted(results) == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_fan_out_collects_results(self) -> None:
        pipeline = Pipeline.from_list([2, 3]).fan_out(lambda value: value + 1, lambda value: value * 2)
        assert await collect(pipeline) == [[3, 4], [4, 6]]

    @pytest.mark.asyncio
    async def test_throttle_drops_rapid_values(self) -> None:
        pipeline = Pipeline.from_list([1, 2, 3]).throttle(0.5)
        assert await collect(pipeline) == [1]

    @pytest.mark.asyncio
    async def test_debounce_emits_latest_value_after_quiet_period(self) -> None:
        source = Pipeline.from_fn(lambda: DelayedIterator([1, 2, 3], [0.0, 0.01, 0.01]))
        assert await collect(source.debounce(0.03)) == [3]

    @pytest.mark.asyncio
    async def test_distinct_take_skip_chain(self) -> None:
        pipeline = Pipeline.from_list([1, 1, 2, 2, 3, 4]).distinct().skip(1).take(2)
        assert await collect(pipeline) == [2, 3]

    @pytest.mark.asyncio
    async def test_partition_splits_source_once(self) -> None:
        source = Pipeline.from_list([1, 2, 3, 4, 5])
        evens, odds = source.partition(lambda value: value % 2 == 0)
        assert await collect(evens) == [2, 4]
        assert await collect(odds) == [1, 3, 5]

    @pytest.mark.asyncio
    async def test_buffer_preserves_values(self) -> None:
        pipeline = Pipeline.from_list([1, 2, 3]).buffer(2)
        assert await collect(pipeline) == [1, 2, 3]

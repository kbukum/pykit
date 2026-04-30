# mypy: ignore-errors
"""Comprehensive tests for the pykit_pipeline package."""

from __future__ import annotations

import pytest

from pykit_pipeline import Pipeline, PipelineIterator, collect, concat, drain, for_each, reduce

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class CountingIterator(PipelineIterator[int]):
    """Concrete subclass that yields integers 1..n, then None."""

    def __init__(self, n: int) -> None:
        self._n = n
        self._i = 0
        self.closed = False

    async def next(self) -> int | None:
        if self._i >= self._n:
            return None
        self._i += 1
        return self._i

    async def close(self) -> None:
        self.closed = True


class _SliceHelper(PipelineIterator[int]):
    """Wraps a list so flat_map tests can produce sub-iterators."""

    def __init__(self, items: list[int]) -> None:
        self._items = items
        self._idx = 0

    async def next(self) -> int | None:
        if self._idx >= len(self._items):
            return None
        val = self._items[self._idx]
        self._idx += 1
        return val


# ===========================================================================
# 1. PipelineIterator — abstract interface via concrete subclass
# ===========================================================================


class TestPipelineIterator:
    @pytest.mark.asyncio
    async def test_next_returns_values_then_none(self) -> None:
        it = CountingIterator(3)
        assert await it.next() == 1
        assert await it.next() == 2
        assert await it.next() == 3
        assert await it.next() is None

    @pytest.mark.asyncio
    async def test_aiter_protocol(self) -> None:
        it = CountingIterator(3)
        result: list[int] = []
        async for val in it:
            result.append(val)
        assert result == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_close_called(self) -> None:
        it = CountingIterator(1)
        assert not it.closed
        await it.close()
        assert it.closed

    @pytest.mark.asyncio
    async def test_empty_iterator(self) -> None:
        it = CountingIterator(0)
        assert await it.next() is None

    @pytest.mark.asyncio
    async def test_aiter_returns_self(self) -> None:
        it = CountingIterator(1)
        assert it.__aiter__() is it


# ===========================================================================
# 2. Pipeline.from_list
# ===========================================================================


class TestFromList:
    @pytest.mark.asyncio
    async def test_basic(self) -> None:
        assert await collect(Pipeline.from_list([1, 2, 3])) == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_empty_list(self) -> None:
        assert await collect(Pipeline.from_list([])) == []

    @pytest.mark.asyncio
    async def test_single_element(self) -> None:
        assert await collect(Pipeline.from_list([42])) == [42]

    @pytest.mark.asyncio
    async def test_strings(self) -> None:
        assert await collect(Pipeline.from_list(["a", "b"])) == ["a", "b"]

    @pytest.mark.asyncio
    async def test_reusable(self) -> None:
        """from_list pipelines can be iterated multiple times."""
        p = Pipeline.from_list([1, 2])
        assert await collect(p) == [1, 2]
        assert await collect(p) == [1, 2]

    @pytest.mark.asyncio
    async def test_does_not_mutate_source(self) -> None:
        src = [1, 2, 3]
        p = Pipeline.from_list(src)
        await collect(p)
        assert src == [1, 2, 3]


# ===========================================================================
# 3. Pipeline.from_fn
# ===========================================================================


class TestFromFn:
    @pytest.mark.asyncio
    async def test_basic(self) -> None:
        p = Pipeline.from_fn(lambda: CountingIterator(3))
        assert await collect(p) == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_reusable(self) -> None:
        p = Pipeline.from_fn(lambda: CountingIterator(2))
        assert await collect(p) == [1, 2]
        assert await collect(p) == [1, 2]

    @pytest.mark.asyncio
    async def test_factory_called_each_time(self) -> None:
        call_count = 0

        def factory() -> CountingIterator:
            nonlocal call_count
            call_count += 1
            return CountingIterator(1)

        p = Pipeline.from_fn(factory)
        await collect(p)
        await collect(p)
        assert call_count == 2


# ===========================================================================
# 4. Pipeline.from_iter — consumed-once semantics
# ===========================================================================


class TestFromIter:
    @pytest.mark.asyncio
    async def test_basic(self) -> None:
        it = CountingIterator(3)
        p = Pipeline.from_iter(it)
        assert await collect(p) == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_consumed_once(self) -> None:
        it = CountingIterator(3)
        p = Pipeline.from_iter(it)
        assert await collect(p) == [1, 2, 3]
        # Second collect yields empty — iterator was consumed
        assert await collect(p) == []

    @pytest.mark.asyncio
    async def test_empty_iter(self) -> None:
        it = CountingIterator(0)
        p = Pipeline.from_iter(it)
        assert await collect(p) == []


# ===========================================================================
# 5. Pipeline.map
# ===========================================================================


class TestMap:
    @pytest.mark.asyncio
    async def test_double(self) -> None:
        p = Pipeline.from_list([1, 2, 3]).map(lambda x: x * 2)
        assert await collect(p) == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_type_change(self) -> None:
        p = Pipeline.from_list([1, 2, 3]).map(str)
        assert await collect(p) == ["1", "2", "3"]

    @pytest.mark.asyncio
    async def test_on_empty(self) -> None:
        p = Pipeline.from_list([]).map(lambda x: x * 10)
        assert await collect(p) == []

    @pytest.mark.asyncio
    async def test_chained_maps(self) -> None:
        p = Pipeline.from_list([1, 2]).map(lambda x: x + 1).map(lambda x: x * 10)
        assert await collect(p) == [20, 30]

    @pytest.mark.asyncio
    async def test_identity(self) -> None:
        p = Pipeline.from_list([5, 6, 7]).map(lambda x: x)
        assert await collect(p) == [5, 6, 7]


# ===========================================================================
# 6. Pipeline.filter
# ===========================================================================


class TestFilter:
    @pytest.mark.asyncio
    async def test_even(self) -> None:
        p = Pipeline.from_list([1, 2, 3, 4, 5]).filter(lambda x: x % 2 == 0)
        assert await collect(p) == [2, 4]

    @pytest.mark.asyncio
    async def test_none_match(self) -> None:
        p = Pipeline.from_list([1, 3, 5]).filter(lambda x: x % 2 == 0)
        assert await collect(p) == []

    @pytest.mark.asyncio
    async def test_all_match(self) -> None:
        p = Pipeline.from_list([2, 4]).filter(lambda x: x % 2 == 0)
        assert await collect(p) == [2, 4]

    @pytest.mark.asyncio
    async def test_on_empty(self) -> None:
        p = Pipeline.from_list([]).filter(lambda x: True)
        assert await collect(p) == []

    @pytest.mark.asyncio
    async def test_chained_filters(self) -> None:
        p = Pipeline.from_list(range(1, 21)).filter(lambda x: x % 2 == 0).filter(lambda x: x % 3 == 0)
        assert await collect(p) == [6, 12, 18]


# ===========================================================================
# 7. Pipeline.tap
# ===========================================================================


class TestTap:
    @pytest.mark.asyncio
    async def test_side_effect(self) -> None:
        seen: list[int] = []
        p = Pipeline.from_list([1, 2, 3]).tap(lambda x: seen.append(x))
        result = await collect(p)
        assert result == [1, 2, 3]
        assert seen == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_does_not_change_values(self) -> None:
        p = Pipeline.from_list([10, 20]).tap(lambda _: None)
        assert await collect(p) == [10, 20]

    @pytest.mark.asyncio
    async def test_on_empty(self) -> None:
        called = False

        def mark(_: int) -> None:
            nonlocal called
            called = True

        p = Pipeline.from_list([]).tap(mark)
        assert await collect(p) == []
        assert not called

    @pytest.mark.asyncio
    async def test_tap_chained_with_map(self) -> None:
        log: list[int] = []
        p = Pipeline.from_list([1, 2]).tap(lambda x: log.append(x)).map(lambda x: x * 10)
        assert await collect(p) == [10, 20]
        assert log == [1, 2]


# ===========================================================================
# 8. Pipeline.flat_map
# ===========================================================================


class TestFlatMap:
    @pytest.mark.asyncio
    async def test_expand(self) -> None:
        p = Pipeline.from_list([1, 2, 3]).flat_map(lambda x: _SliceHelper([x, x * 10]))
        assert await collect(p) == [1, 10, 2, 20, 3, 30]

    @pytest.mark.asyncio
    async def test_some_empty(self) -> None:
        """flat_map with sub-iterators that are sometimes empty."""
        p = Pipeline.from_list([1, 2, 3]).flat_map(lambda x: _SliceHelper([x] if x % 2 == 1 else []))
        assert await collect(p) == [1, 3]

    @pytest.mark.asyncio
    async def test_all_empty(self) -> None:
        p = Pipeline.from_list([1, 2]).flat_map(lambda _: _SliceHelper([]))
        assert await collect(p) == []

    @pytest.mark.asyncio
    async def test_on_empty_source(self) -> None:
        p = Pipeline.from_list([]).flat_map(lambda x: _SliceHelper([x]))
        assert await collect(p) == []

    @pytest.mark.asyncio
    async def test_single_element_per_sub(self) -> None:
        p = Pipeline.from_list([10, 20]).flat_map(lambda x: _SliceHelper([x]))
        assert await collect(p) == [10, 20]


# ===========================================================================
# 9. collect
# ===========================================================================


class TestCollect:
    @pytest.mark.asyncio
    async def test_returns_list(self) -> None:
        result = await collect(Pipeline.from_list([1, 2]))
        assert isinstance(result, list)
        assert result == [1, 2]

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        assert await collect(Pipeline.from_list([])) == []


# ===========================================================================
# 10. drain — sync and async sinks
# ===========================================================================


class TestDrain:
    @pytest.mark.asyncio
    async def test_sync_sink(self) -> None:
        received: list[int] = []
        await drain(Pipeline.from_list([1, 2, 3]), lambda x: received.append(x))
        assert received == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_async_sink(self) -> None:
        received: list[int] = []

        async def async_sink(x: int) -> None:
            received.append(x)

        await drain(Pipeline.from_list([4, 5, 6]), async_sink)
        assert received == [4, 5, 6]

    @pytest.mark.asyncio
    async def test_empty_pipeline(self) -> None:
        called = False

        def sink(_: int) -> None:
            nonlocal called
            called = True

        await drain(Pipeline.from_list([]), sink)
        assert not called


# ===========================================================================
# 11. for_each — alias for drain
# ===========================================================================


class TestForEach:
    @pytest.mark.asyncio
    async def test_sync_fn(self) -> None:
        received: list[int] = []
        await for_each(Pipeline.from_list([7, 8]), lambda x: received.append(x))
        assert received == [7, 8]

    @pytest.mark.asyncio
    async def test_async_fn(self) -> None:
        received: list[str] = []

        async def fn(x: str) -> None:
            received.append(x)

        await for_each(Pipeline.from_list(["a", "b"]), fn)
        assert received == ["a", "b"]

    @pytest.mark.asyncio
    async def test_empty(self) -> None:
        await for_each(Pipeline.from_list([]), lambda x: None)


# ===========================================================================
# 12. concat
# ===========================================================================


class TestConcat:
    @pytest.mark.asyncio
    async def test_two_pipelines(self) -> None:
        a = Pipeline.from_list([1, 2])
        b = Pipeline.from_list([3, 4])
        assert await collect(concat(a, b)) == [1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_three_pipelines(self) -> None:
        a = Pipeline.from_list([1])
        b = Pipeline.from_list([2])
        c = Pipeline.from_list([3])
        assert await collect(concat(a, b, c)) == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_with_empty_pipelines(self) -> None:
        a = Pipeline.from_list([])
        b = Pipeline.from_list([1])
        c = Pipeline.from_list([])
        assert await collect(concat(a, b, c)) == [1]

    @pytest.mark.asyncio
    async def test_all_empty(self) -> None:
        a = Pipeline.from_list([])
        b = Pipeline.from_list([])
        assert await collect(concat(a, b)) == []

    @pytest.mark.asyncio
    async def test_single_pipeline(self) -> None:
        a = Pipeline.from_list([1, 2])
        assert await collect(concat(a)) == [1, 2]

    @pytest.mark.asyncio
    async def test_concat_preserves_order(self) -> None:
        a = Pipeline.from_list([3, 1])
        b = Pipeline.from_list([4, 2])
        assert await collect(concat(a, b)) == [3, 1, 4, 2]


# ===========================================================================
# 13. reduce
# ===========================================================================


class TestReduce:
    @pytest.mark.asyncio
    async def test_sum(self) -> None:
        p = reduce(Pipeline.from_list([1, 2, 3, 4]), 0, lambda acc, x: acc + x)
        assert await collect(p) == [10]

    @pytest.mark.asyncio
    async def test_product(self) -> None:
        p = reduce(Pipeline.from_list([2, 3, 4]), 1, lambda acc, x: acc * x)
        assert await collect(p) == [24]

    @pytest.mark.asyncio
    async def test_string_concat(self) -> None:
        p = reduce(Pipeline.from_list(["a", "b", "c"]), "", lambda acc, x: acc + x)
        assert await collect(p) == ["abc"]

    @pytest.mark.asyncio
    async def test_empty_returns_init(self) -> None:
        p = reduce(Pipeline.from_list([]), 99, lambda acc, x: acc + x)
        assert await collect(p) == [99]

    @pytest.mark.asyncio
    async def test_single_element(self) -> None:
        p = reduce(Pipeline.from_list([5]), 0, lambda acc, x: acc + x)
        assert await collect(p) == [5]

    @pytest.mark.asyncio
    async def test_reduce_consumed_once(self) -> None:
        """reduce returns a pipeline that yields exactly one value."""
        p = reduce(Pipeline.from_list([1, 2]), 0, lambda a, x: a + x)
        it = p.iter()
        assert await it.next() == 3
        assert await it.next() is None
        await it.close()


# ===========================================================================
# 14. Edge cases & chained operations
# ===========================================================================


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_large_list(self) -> None:
        n = 10_000
        p = Pipeline.from_list(list(range(n)))
        result = await collect(p)
        assert len(result) == n
        assert result[0] == 0
        assert result[-1] == n - 1

    @pytest.mark.asyncio
    async def test_map_filter_reduce_chain(self) -> None:
        """Chain: double → keep evens → sum."""
        p = Pipeline.from_list([1, 2, 3, 4, 5])
        doubled = p.map(lambda x: x * 2)  # [2, 4, 6, 8, 10]
        evens = doubled.filter(lambda x: x % 4 == 0)  # [4, 8]
        total = reduce(evens, 0, lambda a, x: a + x)
        assert await collect(total) == [12]

    @pytest.mark.asyncio
    async def test_map_filter_collect(self) -> None:
        result = await collect(Pipeline.from_list(range(1, 11)).map(lambda x: x**2).filter(lambda x: x > 20))
        assert result == [25, 36, 49, 64, 81, 100]

    @pytest.mark.asyncio
    async def test_tap_does_not_affect_chain(self) -> None:
        log: list[int] = []
        result = await collect(
            Pipeline.from_list([1, 2, 3])
            .tap(lambda x: log.append(x))
            .map(lambda x: x + 10)
            .filter(lambda x: x > 11)
        )
        assert result == [12, 13]
        assert log == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_flat_map_then_reduce(self) -> None:
        p = Pipeline.from_list([1, 2]).flat_map(lambda x: _SliceHelper([x, x]))
        total = reduce(p, 0, lambda a, x: a + x)
        assert await collect(total) == [6]  # 1+1+2+2

    @pytest.mark.asyncio
    async def test_concat_then_map(self) -> None:
        combined = concat(
            Pipeline.from_list([1, 2]),
            Pipeline.from_list([3, 4]),
        ).map(lambda x: x * 100)
        assert await collect(combined) == [100, 200, 300, 400]

    @pytest.mark.asyncio
    async def test_iter_method_returns_pipeline_iterator(self) -> None:
        p = Pipeline.from_list([1])
        it = p.iter()
        assert isinstance(it, PipelineIterator)
        assert await it.next() == 1
        assert await it.next() is None
        await it.close()

    @pytest.mark.asyncio
    async def test_from_list_with_range(self) -> None:
        p = Pipeline.from_list(list(range(5)))
        assert await collect(p) == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_filter_then_flat_map(self) -> None:
        p = (
            Pipeline.from_list([1, 2, 3, 4])
            .filter(lambda x: x % 2 == 0)
            .flat_map(lambda x: _SliceHelper([x, -x]))
        )
        assert await collect(p) == [2, -2, 4, -4]

    @pytest.mark.asyncio
    async def test_multiple_taps(self) -> None:
        log1: list[int] = []
        log2: list[int] = []
        result = await collect(
            Pipeline.from_list([1, 2])
            .tap(lambda x: log1.append(x))
            .map(lambda x: x * 10)
            .tap(lambda x: log2.append(x))
        )
        assert result == [10, 20]
        assert log1 == [1, 2]
        assert log2 == [10, 20]

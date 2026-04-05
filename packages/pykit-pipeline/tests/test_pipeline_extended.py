"""Extended tests for pykit_pipeline — error handling, edge cases, resource cleanup, and chaining."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from pykit_pipeline import Pipeline, PipelineIterator, collect, concat, drain, for_each, reduce


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class TrackingIterator(PipelineIterator[int]):
    """Iterator that tracks next/close calls for verifying lifecycle."""

    def __init__(self, items: list[int]) -> None:
        self._items = items
        self._idx = 0
        self.next_count = 0
        self.closed = False

    async def next(self) -> int | None:
        self.next_count += 1
        if self._idx >= len(self._items):
            return None
        val = self._items[self._idx]
        self._idx += 1
        return val

    async def close(self) -> None:
        self.closed = True


class FailingIterator(PipelineIterator[int]):
    """Iterator that raises after yielding `n` values."""

    def __init__(self, fail_after: int) -> None:
        self._fail_after = fail_after
        self._count = 0
        self.closed = False

    async def next(self) -> int | None:
        if self._count >= self._fail_after:
            raise RuntimeError("iterator exploded")
        self._count += 1
        return self._count

    async def close(self) -> None:
        self.closed = True


class SlowCloseIterator(PipelineIterator[int]):
    """Iterator whose close() is async and tracks call."""

    def __init__(self, items: list[int]) -> None:
        self._items = items
        self._idx = 0
        self.closed = False

    async def next(self) -> int | None:
        if self._idx >= len(self._items):
            return None
        val = self._items[self._idx]
        self._idx += 1
        return val

    async def close(self) -> None:
        await asyncio.sleep(0)  # simulate async cleanup
        self.closed = True


class SubIter(PipelineIterator[int]):
    """Simple list-backed iterator for flat_map tests."""

    def __init__(self, items: list[int]) -> None:
        self._items = items
        self._idx = 0
        self.closed = False

    async def next(self) -> int | None:
        if self._idx >= len(self._items):
            return None
        val = self._items[self._idx]
        self._idx += 1
        return val

    async def close(self) -> None:
        self.closed = True


# ===========================================================================
# 1. Error handling in map
# ===========================================================================


class TestMapErrorHandling:
    async def test_map_exception_propagates(self) -> None:
        p = Pipeline.from_list([1, 2, 3]).map(lambda x: 1 // (x - 2))
        with pytest.raises(ZeroDivisionError):
            await collect(p)

    async def test_map_exception_after_successful_items(self) -> None:
        """Exception on third element; first two would succeed."""
        results: list[int] = []

        def transform(x: int) -> int:
            if x == 3:
                raise ValueError("bad value")
            return x * 10

        p = Pipeline.from_list([1, 2, 3, 4]).map(transform)
        with pytest.raises(ValueError, match="bad value"):
            await collect(p)

    async def test_map_exception_closes_source_iterator(self) -> None:
        tracker = TrackingIterator([1, 2, 3])
        p = Pipeline.from_iter(tracker).map(lambda x: 1 // (x - 2))
        with pytest.raises(ZeroDivisionError):
            await collect(p)
        assert tracker.closed

    async def test_map_with_none_return(self) -> None:
        """map returning None causes pipeline to stop (None = end sentinel)."""
        p = Pipeline.from_list([1, 2, 3]).map(lambda x: None if x == 2 else x)
        result = await collect(p)
        # Pipeline stops when it sees None from map
        assert result == [1]

    @pytest.mark.parametrize(
        "fn,exc_type",
        [
            (lambda x: x / 0, ZeroDivisionError),
            (lambda x: int("not_a_number"), ValueError),
            (lambda x: [][99], IndexError),
            (lambda x: {}["missing"], KeyError),
        ],
        ids=["division", "value_error", "index_error", "key_error"],
    )
    async def test_map_various_exception_types(self, fn: Callable, exc_type: type) -> None:
        p = Pipeline.from_list([1]).map(fn)
        with pytest.raises(exc_type):
            await collect(p)


# ===========================================================================
# 2. Error handling in filter
# ===========================================================================


class TestFilterErrorHandling:
    async def test_filter_exception_propagates(self) -> None:
        def bad_pred(x: int) -> bool:
            if x == 2:
                raise RuntimeError("filter boom")
            return True

        p = Pipeline.from_list([1, 2, 3]).filter(bad_pred)
        with pytest.raises(RuntimeError, match="filter boom"):
            await collect(p)

    async def test_filter_exception_closes_source(self) -> None:
        tracker = TrackingIterator([1, 2, 3])

        def bad_pred(x: int) -> bool:
            if x == 2:
                raise RuntimeError("oops")
            return True

        p = Pipeline.from_iter(tracker).filter(bad_pred)
        with pytest.raises(RuntimeError):
            await collect(p)
        assert tracker.closed

    @pytest.mark.parametrize(
        "predicate,expected",
        [
            (lambda x: x > 0, [1, 2, 3]),
            (lambda x: x < 0, []),
            (lambda x: x == 2, [2]),
        ],
        ids=["all_pass", "none_pass", "one_pass"],
    )
    async def test_filter_parametrized(self, predicate: Callable, expected: list[int]) -> None:
        result = await collect(Pipeline.from_list([1, 2, 3]).filter(predicate))
        assert result == expected


# ===========================================================================
# 3. Error handling in tap
# ===========================================================================


class TestTapErrorHandling:
    async def test_tap_exception_propagates(self) -> None:
        def bad_fn(x: int) -> None:
            if x == 2:
                raise ValueError("tap error")

        p = Pipeline.from_list([1, 2, 3]).tap(bad_fn)
        with pytest.raises(ValueError, match="tap error"):
            await collect(p)

    async def test_tap_exception_closes_source(self) -> None:
        tracker = TrackingIterator([1, 2, 3])

        def bad_fn(x: int) -> None:
            if x == 2:
                raise ValueError("tap boom")

        p = Pipeline.from_iter(tracker).tap(bad_fn)
        with pytest.raises(ValueError):
            await collect(p)
        assert tracker.closed


# ===========================================================================
# 4. Error handling in flat_map
# ===========================================================================


class TestFlatMapErrorHandling:
    async def test_flat_map_fn_exception_propagates(self) -> None:
        def bad_fn(x: int) -> PipelineIterator[int]:
            if x == 2:
                raise RuntimeError("flat_map error")
            return SubIter([x])

        p = Pipeline.from_list([1, 2, 3]).flat_map(bad_fn)
        with pytest.raises(RuntimeError, match="flat_map error"):
            await collect(p)

    async def test_flat_map_sub_iterator_exception(self) -> None:
        """Exception inside a sub-iterator propagates."""

        class ExplodingSubIter(PipelineIterator[int]):
            def __init__(self) -> None:
                self._count = 0

            async def next(self) -> int | None:
                if self._count > 0:
                    raise RuntimeError("sub exploded")
                self._count += 1
                return 1

        p = Pipeline.from_list([1]).flat_map(lambda _: ExplodingSubIter())
        with pytest.raises(RuntimeError, match="sub exploded"):
            await collect(p)

    async def test_flat_map_close_propagates(self) -> None:
        tracker = TrackingIterator([1, 2])
        p = Pipeline.from_iter(tracker).flat_map(lambda x: SubIter([x, x * 10]))
        await collect(p)
        assert tracker.closed


# ===========================================================================
# 5. Error handling in drain / for_each
# ===========================================================================


class TestDrainErrorHandling:
    async def test_drain_sync_sink_exception(self) -> None:
        def bad_sink(x: int) -> None:
            if x == 2:
                raise ValueError("sink error")

        with pytest.raises(ValueError, match="sink error"):
            await drain(Pipeline.from_list([1, 2, 3]), bad_sink)

    async def test_drain_async_sink_exception(self) -> None:
        async def bad_sink(x: int) -> None:
            if x == 2:
                raise ValueError("async sink error")

        with pytest.raises(ValueError, match="async sink error"):
            await drain(Pipeline.from_list([1, 2, 3]), bad_sink)

    async def test_drain_closes_iterator_on_sink_error(self) -> None:
        tracker = TrackingIterator([1, 2, 3])

        def bad_sink(x: int) -> None:
            if x == 2:
                raise ValueError("boom")

        with pytest.raises(ValueError):
            await drain(Pipeline.from_iter(tracker), bad_sink)
        assert tracker.closed

    async def test_for_each_sync_exception(self) -> None:
        def bad_fn(x: int) -> None:
            raise RuntimeError("for_each error")

        with pytest.raises(RuntimeError, match="for_each error"):
            await for_each(Pipeline.from_list([1]), bad_fn)

    async def test_for_each_async_exception(self) -> None:
        async def bad_fn(x: int) -> None:
            raise RuntimeError("async for_each error")

        with pytest.raises(RuntimeError, match="async for_each error"):
            await for_each(Pipeline.from_list([1]), bad_fn)


# ===========================================================================
# 6. Error handling in reduce
# ===========================================================================


class TestReduceErrorHandling:
    async def test_reduce_fn_exception_propagates(self) -> None:
        def bad_fn(acc: int, x: int) -> int:
            if x == 3:
                raise RuntimeError("reduce boom")
            return acc + x

        p = reduce(Pipeline.from_list([1, 2, 3]), 0, bad_fn)
        with pytest.raises(RuntimeError, match="reduce boom"):
            await collect(p)

    async def test_reduce_closes_source_on_error(self) -> None:
        tracker = TrackingIterator([1, 2, 3])

        def bad_fn(acc: int, x: int) -> int:
            if x == 2:
                raise RuntimeError("reduce oops")
            return acc + x

        p = reduce(Pipeline.from_iter(tracker), 0, bad_fn)
        with pytest.raises(RuntimeError):
            await collect(p)
        assert tracker.closed


# ===========================================================================
# 7. Error handling in source iterator
# ===========================================================================


class TestSourceIteratorErrors:
    async def test_failing_source_propagates(self) -> None:
        fail_it = FailingIterator(fail_after=2)
        p = Pipeline.from_iter(fail_it)
        with pytest.raises(RuntimeError, match="iterator exploded"):
            await collect(p)

    async def test_failing_source_closes_iterator(self) -> None:
        fail_it = FailingIterator(fail_after=1)
        p = Pipeline.from_iter(fail_it)
        with pytest.raises(RuntimeError):
            await collect(p)
        assert fail_it.closed

    async def test_failing_source_through_map(self) -> None:
        fail_it = FailingIterator(fail_after=1)
        p = Pipeline.from_iter(fail_it).map(lambda x: x * 2)
        with pytest.raises(RuntimeError, match="iterator exploded"):
            await collect(p)


# ===========================================================================
# 8. Resource cleanup / close propagation
# ===========================================================================


class TestResourceCleanup:
    async def test_collect_calls_close(self) -> None:
        tracker = TrackingIterator([1, 2])
        await collect(Pipeline.from_iter(tracker))
        assert tracker.closed

    async def test_drain_calls_close(self) -> None:
        tracker = TrackingIterator([1, 2])
        await drain(Pipeline.from_iter(tracker), lambda x: None)
        assert tracker.closed

    async def test_for_each_calls_close(self) -> None:
        tracker = TrackingIterator([1, 2])
        await for_each(Pipeline.from_iter(tracker), lambda x: None)
        assert tracker.closed

    async def test_close_called_on_empty_pipeline(self) -> None:
        tracker = TrackingIterator([])
        await collect(Pipeline.from_iter(tracker))
        assert tracker.closed

    async def test_slow_close_is_awaited(self) -> None:
        slow = SlowCloseIterator([1, 2])
        await collect(Pipeline.from_iter(slow))
        assert slow.closed

    async def test_close_propagates_through_map(self) -> None:
        tracker = TrackingIterator([1, 2])
        p = Pipeline.from_iter(tracker).map(lambda x: x * 2)
        it = p.iter()
        await it.next()
        await it.close()
        assert tracker.closed

    async def test_close_propagates_through_filter(self) -> None:
        tracker = TrackingIterator([1, 2])
        p = Pipeline.from_iter(tracker).filter(lambda x: True)
        it = p.iter()
        await it.next()
        await it.close()
        assert tracker.closed

    async def test_close_propagates_through_tap(self) -> None:
        tracker = TrackingIterator([1, 2])
        p = Pipeline.from_iter(tracker).tap(lambda x: None)
        it = p.iter()
        await it.next()
        await it.close()
        assert tracker.closed

    async def test_close_propagates_through_flat_map(self) -> None:
        tracker = TrackingIterator([1, 2])
        p = Pipeline.from_iter(tracker).flat_map(lambda x: SubIter([x]))
        it = p.iter()
        await it.next()
        await it.close()
        assert tracker.closed

    async def test_concat_close_all_iterators(self) -> None:
        t1 = TrackingIterator([1])
        t2 = TrackingIterator([2])
        p = concat(Pipeline.from_iter(t1), Pipeline.from_iter(t2))
        await collect(p)
        assert t1.closed
        assert t2.closed

    async def test_reduce_close_propagates(self) -> None:
        tracker = TrackingIterator([1, 2, 3])
        p = reduce(Pipeline.from_iter(tracker), 0, lambda a, x: a + x)
        await collect(p)
        assert tracker.closed


# ===========================================================================
# 9. Edge cases: empty pipelines
# ===========================================================================


class TestEmptyPipelines:
    async def test_map_on_empty(self) -> None:
        assert await collect(Pipeline.from_list([]).map(lambda x: x * 2)) == []

    async def test_filter_on_empty(self) -> None:
        assert await collect(Pipeline.from_list([]).filter(lambda x: True)) == []

    async def test_tap_on_empty(self) -> None:
        called = False
        p = Pipeline.from_list([]).tap(lambda x: None)
        assert await collect(p) == []

    async def test_flat_map_on_empty(self) -> None:
        assert await collect(Pipeline.from_list([]).flat_map(lambda x: SubIter([x]))) == []

    async def test_reduce_on_empty(self) -> None:
        p = reduce(Pipeline.from_list([]), 42, lambda a, x: a + x)
        assert await collect(p) == [42]

    async def test_concat_all_empty(self) -> None:
        p = concat(Pipeline.from_list([]), Pipeline.from_list([]), Pipeline.from_list([]))
        assert await collect(p) == []

    async def test_chain_on_empty(self) -> None:
        p = Pipeline.from_list([]).map(lambda x: x * 2).filter(lambda x: True).tap(lambda x: None)
        assert await collect(p) == []


# ===========================================================================
# 10. Edge cases: single element
# ===========================================================================


class TestSingleElement:
    async def test_map_single(self) -> None:
        assert await collect(Pipeline.from_list([42]).map(lambda x: x + 1)) == [43]

    async def test_filter_single_pass(self) -> None:
        assert await collect(Pipeline.from_list([42]).filter(lambda x: True)) == [42]

    async def test_filter_single_reject(self) -> None:
        assert await collect(Pipeline.from_list([42]).filter(lambda x: False)) == []

    async def test_flat_map_single(self) -> None:
        result = await collect(Pipeline.from_list([5]).flat_map(lambda x: SubIter([x, x * 2])))
        assert result == [5, 10]

    async def test_reduce_single(self) -> None:
        p = reduce(Pipeline.from_list([7]), 0, lambda a, x: a + x)
        assert await collect(p) == [7]

    async def test_concat_single_pipeline_single_elem(self) -> None:
        assert await collect(concat(Pipeline.from_list([99]))) == [99]

    async def test_tap_single(self) -> None:
        seen: list[int] = []
        result = await collect(Pipeline.from_list([1]).tap(lambda x: seen.append(x)))
        assert result == [1]
        assert seen == [1]


# ===========================================================================
# 11. Large streams
# ===========================================================================


class TestLargeStreams:
    async def test_large_map(self) -> None:
        n = 50_000
        result = await collect(Pipeline.from_list(list(range(n))).map(lambda x: x + 1))
        assert len(result) == n
        assert result[0] == 1
        assert result[-1] == n

    async def test_large_filter(self) -> None:
        n = 50_000
        result = await collect(Pipeline.from_list(list(range(n))).filter(lambda x: x % 2 == 0))
        assert len(result) == n // 2

    async def test_large_chain(self) -> None:
        n = 10_000
        result = await collect(
            Pipeline.from_list(list(range(n)))
            .map(lambda x: x * 2)
            .filter(lambda x: x % 4 == 0)
        )
        assert len(result) == n // 2

    async def test_large_reduce(self) -> None:
        n = 10_000
        p = reduce(Pipeline.from_list(list(range(1, n + 1))), 0, lambda a, x: a + x)
        result = await collect(p)
        assert result == [n * (n + 1) // 2]


# ===========================================================================
# 12. PipelineIterator protocol edge cases
# ===========================================================================


class TestPipelineIteratorProtocol:
    async def test_anext_raises_stop_async_iteration(self) -> None:
        it = TrackingIterator([1])
        assert await it.__anext__() == 1
        with pytest.raises(StopAsyncIteration):
            await it.__anext__()

    async def test_aiter_returns_self(self) -> None:
        it = TrackingIterator([])
        assert it.__aiter__() is it

    async def test_empty_iterator_immediate_stop(self) -> None:
        it = TrackingIterator([])
        with pytest.raises(StopAsyncIteration):
            await it.__anext__()

    async def test_async_for_loop(self) -> None:
        it = TrackingIterator([10, 20, 30])
        collected: list[int] = []
        async for val in it:
            collected.append(val)
        assert collected == [10, 20, 30]

    async def test_next_after_exhaustion_stays_none(self) -> None:
        it = TrackingIterator([1])
        assert await it.next() == 1
        assert await it.next() is None
        assert await it.next() is None  # stays exhausted


# ===========================================================================
# 13. from_iter consumed-once semantics
# ===========================================================================


class TestFromIterConsumedOnce:
    async def test_second_collect_empty(self) -> None:
        it = TrackingIterator([1, 2, 3])
        p = Pipeline.from_iter(it)
        first = await collect(p)
        second = await collect(p)
        assert first == [1, 2, 3]
        assert second == []

    async def test_from_iter_with_map(self) -> None:
        it = TrackingIterator([1, 2])
        p = Pipeline.from_iter(it).map(lambda x: x * 10)
        assert await collect(p) == [10, 20]
        assert await collect(p) == []

    async def test_from_iter_empty(self) -> None:
        it = TrackingIterator([])
        p = Pipeline.from_iter(it)
        assert await collect(p) == []
        assert await collect(p) == []


# ===========================================================================
# 14. from_fn reusability
# ===========================================================================


class TestFromFnReuse:
    async def test_factory_creates_fresh_iterator_each_time(self) -> None:
        calls: list[int] = []

        def factory() -> TrackingIterator:
            calls.append(1)
            return TrackingIterator([10, 20])

        p = Pipeline.from_fn(factory)
        r1 = await collect(p)
        r2 = await collect(p)
        assert r1 == [10, 20]
        assert r2 == [10, 20]
        assert len(calls) == 2

    async def test_from_fn_with_operators(self) -> None:
        p = Pipeline.from_fn(lambda: TrackingIterator([1, 2, 3])).map(lambda x: x + 10).filter(lambda x: x > 11)
        r1 = await collect(p)
        r2 = await collect(p)
        assert r1 == [12, 13]
        assert r2 == [12, 13]


# ===========================================================================
# 15. Complex operator chains
# ===========================================================================


class TestComplexChains:
    async def test_map_filter_tap_flat_map_reduce(self) -> None:
        tapped: list[int] = []
        p = (
            Pipeline.from_list([1, 2, 3, 4, 5])
            .map(lambda x: x * 2)        # [2, 4, 6, 8, 10]
            .filter(lambda x: x > 4)     # [6, 8, 10]
            .tap(lambda x: tapped.append(x))
            .flat_map(lambda x: SubIter([x, x + 1]))  # [6,7, 8,9, 10,11]
        )
        result = await collect(p)
        assert result == [6, 7, 8, 9, 10, 11]
        assert tapped == [6, 8, 10]

    async def test_concat_then_filter_map(self) -> None:
        p = (
            concat(Pipeline.from_list([1, 2, 3]), Pipeline.from_list([4, 5, 6]))
            .filter(lambda x: x % 2 == 1)
            .map(lambda x: x * 100)
        )
        assert await collect(p) == [100, 300, 500]

    async def test_nested_flat_map(self) -> None:
        p = (
            Pipeline.from_list([1, 2])
            .flat_map(lambda x: SubIter([x, x * 10]))
            .flat_map(lambda x: SubIter([x, -x]))
        )
        assert await collect(p) == [1, -1, 10, -10, 2, -2, 20, -20]

    async def test_reduce_after_complex_chain(self) -> None:
        p = (
            Pipeline.from_list([1, 2, 3, 4, 5])
            .filter(lambda x: x % 2 == 0)
            .map(lambda x: x * 10)
        )
        total = reduce(p, 0, lambda a, x: a + x)
        assert await collect(total) == [60]  # (2*10) + (4*10)

    async def test_multiple_maps(self) -> None:
        p = Pipeline.from_list([1]).map(lambda x: x + 1).map(lambda x: x * 2).map(lambda x: x + 3).map(str)
        assert await collect(p) == ["7"]

    async def test_multiple_filters(self) -> None:
        p = (
            Pipeline.from_list(list(range(100)))
            .filter(lambda x: x % 2 == 0)
            .filter(lambda x: x % 3 == 0)
            .filter(lambda x: x % 5 == 0)
        )
        # Multiples of 30 under 100
        assert await collect(p) == [0, 30, 60, 90]

    async def test_tap_between_operators_ordering(self) -> None:
        pre_filter: list[int] = []
        post_filter: list[int] = []
        p = (
            Pipeline.from_list([1, 2, 3, 4])
            .tap(lambda x: pre_filter.append(x))
            .filter(lambda x: x > 2)
            .tap(lambda x: post_filter.append(x))
        )
        result = await collect(p)
        assert result == [3, 4]
        assert pre_filter == [1, 2, 3, 4]
        assert post_filter == [3, 4]


# ===========================================================================
# 16. concat edge cases
# ===========================================================================


class TestConcatExtended:
    async def test_concat_no_args(self) -> None:
        """concat() with no pipelines yields empty."""
        p = concat()
        assert await collect(p) == []

    async def test_concat_many_pipelines(self) -> None:
        pipelines = [Pipeline.from_list([i]) for i in range(20)]
        result = await collect(concat(*pipelines))
        assert result == list(range(20))

    async def test_concat_preserves_element_types(self) -> None:
        a = Pipeline.from_list(["hello"])
        b = Pipeline.from_list(["world"])
        assert await collect(concat(a, b)) == ["hello", "world"]

    async def test_concat_with_mapped_pipelines(self) -> None:
        a = Pipeline.from_list([1, 2]).map(lambda x: x * 10)
        b = Pipeline.from_list([3, 4]).map(lambda x: x * 100)
        assert await collect(concat(a, b)) == [10, 20, 300, 400]

    async def test_concat_interleaved_empty(self) -> None:
        p = concat(
            Pipeline.from_list([]),
            Pipeline.from_list([1]),
            Pipeline.from_list([]),
            Pipeline.from_list([2]),
            Pipeline.from_list([]),
        )
        assert await collect(p) == [1, 2]


# ===========================================================================
# 17. reduce edge cases
# ===========================================================================


class TestReduceExtended:
    async def test_reduce_builds_list(self) -> None:
        p = reduce(
            Pipeline.from_list([1, 2, 3]),
            [],
            lambda acc, x: acc + [x * 2],
        )
        assert await collect(p) == [[2, 4, 6]]

    async def test_reduce_builds_dict(self) -> None:
        p = reduce(
            Pipeline.from_list(["a", "bb", "ccc"]),
            {},
            lambda acc, x: {**acc, x: len(x)},
        )
        result = await collect(p)
        assert result == [{"a": 1, "bb": 2, "ccc": 3}]

    async def test_reduce_max(self) -> None:
        p = reduce(Pipeline.from_list([3, 1, 4, 1, 5]), float("-inf"), lambda a, x: max(a, x))
        result = await collect(p)
        assert result == [5]

    async def test_reduce_pipeline_yields_one_value(self) -> None:
        """Reduce iterator yields exactly one value then None."""
        p = reduce(Pipeline.from_list([1, 2]), 0, lambda a, x: a + x)
        it = p.iter()
        v1 = await it.next()
        v2 = await it.next()
        v3 = await it.next()
        assert v1 == 3
        assert v2 is None
        assert v3 is None
        await it.close()


# ===========================================================================
# 18. Type diversity
# ===========================================================================


class TestTypeDiversity:
    async def test_string_pipeline(self) -> None:
        p = Pipeline.from_list(["hello", "world"]).map(str.upper)
        assert await collect(p) == ["HELLO", "WORLD"]

    async def test_float_pipeline(self) -> None:
        p = Pipeline.from_list([1.5, 2.5, 3.5]).map(lambda x: x * 2)
        assert await collect(p) == [3.0, 5.0, 7.0]

    async def test_tuple_pipeline(self) -> None:
        p = Pipeline.from_list([(1, "a"), (2, "b")]).map(lambda t: t[0])
        assert await collect(p) == [1, 2]

    async def test_dict_pipeline(self) -> None:
        p = Pipeline.from_list([{"x": 1}, {"x": 2}]).map(lambda d: d["x"])
        assert await collect(p) == [1, 2]

    async def test_boolean_pipeline(self) -> None:
        """Booleans are truthy/falsy but not None, so they pass through."""
        p = Pipeline.from_list([True, False, True])
        result = await collect(p)
        # False is falsy but not None; pipeline uses `is None` check
        assert result == [True, False, True]

    async def test_nested_list_pipeline(self) -> None:
        p = Pipeline.from_list([[1, 2], [3, 4]]).map(lambda x: sum(x))
        assert await collect(p) == [3, 7]

    @pytest.mark.parametrize(
        "items,map_fn,expected",
        [
            ([1, 2, 3], str, ["1", "2", "3"]),
            (["a", "b"], str.upper, ["A", "B"]),
            ([1.0, 2.0], int, [1, 2]),
            ([(1,), (2,)], lambda x: x[0], [1, 2]),
        ],
        ids=["int_to_str", "str_upper", "float_to_int", "tuple_first"],
    )
    async def test_map_type_conversions(self, items: list, map_fn: Callable, expected: list) -> None:
        assert await collect(Pipeline.from_list(items).map(map_fn)) == expected


# ===========================================================================
# 19. Partial consumption / iterator lifecycle
# ===========================================================================


class TestPartialConsumption:
    async def test_partial_read_via_iter(self) -> None:
        it = Pipeline.from_list([1, 2, 3, 4, 5]).iter()
        assert await it.next() == 1
        assert await it.next() == 2
        await it.close()
        # After close, no requirement to continue, just verify we got 2 values

    async def test_iter_manual_full_read(self) -> None:
        it = Pipeline.from_list([1, 2]).iter()
        vals: list[int] = []
        while True:
            v = await it.next()
            if v is None:
                break
            vals.append(v)
        await it.close()
        assert vals == [1, 2]

    async def test_close_on_flat_map_mid_sub(self) -> None:
        """Close during flat_map while sub-iterator still has values."""
        sub = SubIter([10, 20, 30])
        p = Pipeline.from_list([1]).flat_map(lambda _: sub)
        it = p.iter()
        assert await it.next() == 10
        await it.close()
        assert sub.closed


# ===========================================================================
# 20. Drain and for_each with various callable types
# ===========================================================================


class TestDrainCallables:
    async def test_drain_with_method(self) -> None:
        results: list[int] = []
        await drain(Pipeline.from_list([1, 2, 3]), results.append)
        assert results == [1, 2, 3]

    async def test_drain_with_async_sleep(self) -> None:
        received: list[int] = []

        async def slow_sink(x: int) -> None:
            await asyncio.sleep(0)
            received.append(x)

        await drain(Pipeline.from_list([1, 2]), slow_sink)
        assert received == [1, 2]

    async def test_for_each_with_async_sleep(self) -> None:
        received: list[int] = []

        async def slow_fn(x: int) -> None:
            await asyncio.sleep(0)
            received.append(x)

        await for_each(Pipeline.from_list([10, 20]), slow_fn)
        assert received == [10, 20]


# ===========================================================================
# 21. Parametrized table-driven tests
# ===========================================================================


class TestParametrized:
    @pytest.mark.parametrize(
        "source,expected",
        [
            ([], []),
            ([1], [1]),
            ([1, 2, 3], [1, 2, 3]),
            (list(range(100)), list(range(100))),
        ],
        ids=["empty", "single", "triple", "hundred"],
    )
    async def test_from_list_collect_identity(self, source: list[int], expected: list[int]) -> None:
        assert await collect(Pipeline.from_list(source)) == expected

    @pytest.mark.parametrize(
        "source,fn,expected",
        [
            ([1, 2, 3], lambda x: x * 2, [2, 4, 6]),
            ([1, 2, 3], lambda x: x + 10, [11, 12, 13]),
            ([1, 2, 3], lambda x: -x, [-1, -2, -3]),
            ([1, 2, 3], lambda x: x ** 2, [1, 4, 9]),
        ],
        ids=["double", "add10", "negate", "square"],
    )
    async def test_map_transformations(self, source: list[int], fn: Callable, expected: list[int]) -> None:
        assert await collect(Pipeline.from_list(source).map(fn)) == expected

    @pytest.mark.parametrize(
        "source,pred,expected",
        [
            ([1, 2, 3, 4], lambda x: x > 2, [3, 4]),
            ([1, 2, 3, 4], lambda x: x < 0, []),
            ([1, 2, 3, 4], lambda x: True, [1, 2, 3, 4]),
            ([1, 2, 3, 4], lambda x: x == 2, [2]),
        ],
        ids=["gt2", "none_match", "all_match", "equals_2"],
    )
    async def test_filter_predicates(self, source: list[int], pred: Callable, expected: list[int]) -> None:
        assert await collect(Pipeline.from_list(source).filter(pred)) == expected

    @pytest.mark.parametrize(
        "init,fn,expected",
        [
            (0, lambda a, x: a + x, 15),
            (1, lambda a, x: a * x, 120),
            ("", lambda a, x: a + str(x), "12345"),
        ],
        ids=["sum", "product", "str_concat"],
    )
    async def test_reduce_operations(self, init: Any, fn: Callable, expected: Any) -> None:
        p = reduce(Pipeline.from_list([1, 2, 3, 4, 5]), init, fn)
        assert await collect(p) == [expected]


# ===========================================================================
# 22. _EmptyIter behavior (via from_iter consumed-once)
# ===========================================================================


class TestEmptyIterViaConsumed:
    async def test_double_collect_from_iter(self) -> None:
        """After from_iter is consumed, the internal _EmptyIter kicks in."""
        it = TrackingIterator([1])
        p = Pipeline.from_iter(it)
        assert await collect(p) == [1]
        # Second collect creates _EmptyIter
        assert await collect(p) == []

    async def test_consumed_from_iter_with_map(self) -> None:
        it = TrackingIterator([5])
        p = Pipeline.from_iter(it).map(lambda x: x * 10)
        assert await collect(p) == [50]
        assert await collect(p) == []


# ===========================================================================
# 23. Regression / misc
# ===========================================================================


class TestMiscRegression:
    async def test_from_list_does_not_share_state(self) -> None:
        """Two from_list pipelines from the same list are independent."""
        src = [1, 2, 3]
        p1 = Pipeline.from_list(src)
        p2 = Pipeline.from_list(src)
        assert await collect(p1) == [1, 2, 3]
        assert await collect(p2) == [1, 2, 3]

    async def test_from_list_captures_reference(self) -> None:
        """from_list copies on each iter() call, so mutations before collect are visible."""
        src = [1, 2, 3]
        p = Pipeline.from_list(src)
        src.append(4)
        # The lambda does list(items) lazily — items is the original reference
        assert await collect(p) == [1, 2, 3, 4]

    async def test_flat_map_with_varying_sizes(self) -> None:
        p = Pipeline.from_list([1, 2, 3]).flat_map(
            lambda x: SubIter(list(range(x)))
        )
        # x=1 -> [0], x=2 -> [0,1], x=3 -> [0,1,2]
        assert await collect(p) == [0, 0, 1, 0, 1, 2]

    async def test_pipeline_is_lazy(self) -> None:
        """No work should happen until a terminal is called."""
        call_count = 0

        def counting_map(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x

        p = Pipeline.from_list([1, 2, 3]).map(counting_map)
        assert call_count == 0  # lazy: nothing called yet
        await collect(p)
        assert call_count == 3

    async def test_filter_is_lazy(self) -> None:
        call_count = 0

        def counting_pred(x: int) -> bool:
            nonlocal call_count
            call_count += 1
            return True

        p = Pipeline.from_list([1, 2, 3]).filter(counting_pred)
        assert call_count == 0
        await collect(p)
        assert call_count == 3

    async def test_concat_with_from_fn_and_from_iter(self) -> None:
        it = TrackingIterator([3, 4])
        p = concat(
            Pipeline.from_fn(lambda: TrackingIterator([1, 2])),
            Pipeline.from_iter(it),
        )
        assert await collect(p) == [1, 2, 3, 4]

    async def test_reduce_with_filter_removing_all(self) -> None:
        """Reduce on pipeline that filters everything → returns init."""
        p = Pipeline.from_list([1, 2, 3]).filter(lambda x: False)
        total = reduce(p, 0, lambda a, x: a + x)
        assert await collect(total) == [0]

    async def test_map_returning_zero(self) -> None:
        """Zero is falsy but not None, so it should pass through."""
        p = Pipeline.from_list([1, 2, 3]).map(lambda x: 0)
        assert await collect(p) == [0, 0, 0]

    async def test_map_returning_empty_string(self) -> None:
        """Empty string is falsy but not None."""
        p = Pipeline.from_list([1, 2]).map(lambda x: "")
        assert await collect(p) == ["", ""]

    async def test_map_returning_false(self) -> None:
        """False is falsy but not None."""
        p = Pipeline.from_list([1, 2]).map(lambda x: False)
        assert await collect(p) == [False, False]

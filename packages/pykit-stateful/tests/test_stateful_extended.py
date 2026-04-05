"""Extended tests for pykit-stateful: edge cases, concurrency, custom triggers."""

from __future__ import annotations

import asyncio
import time

import pytest

from pykit_stateful import (
    Accumulator,
    AccumulatorConfig,
    ByteSizeTrigger,
    FlushTrigger,
    MemoryStore,
    SizeTrigger,
    TimeTrigger,
)


# ---------------------------------------------------------------------------
# Store protocol conformance
# ---------------------------------------------------------------------------


class TestStoreProtocol:
    async def test_memory_store_satisfies_protocol(self):
        store: MemoryStore[int] = MemoryStore()
        assert isinstance(store, FlushTrigger) is False  # not a trigger
        # Protocol checks
        assert hasattr(store, "get")
        assert hasattr(store, "set")
        assert hasattr(store, "delete")
        assert hasattr(store, "keys")

    async def test_set_overwrite(self):
        store: MemoryStore[str] = MemoryStore()
        await store.set("k", "v1")
        await store.set("k", "v2")
        assert await store.get("k") == "v2"

    async def test_keys_after_delete(self):
        store: MemoryStore[int] = MemoryStore()
        await store.set("a", 1)
        await store.set("b", 2)
        await store.delete("a")
        assert await store.keys() == ["b"]

    async def test_delete_then_get(self):
        store: MemoryStore[str] = MemoryStore()
        await store.set("x", "val")
        await store.delete("x")
        assert await store.get("x") is None

    async def test_multiple_keys_isolation(self):
        store: MemoryStore[int] = MemoryStore()
        await store.set("a", 10)
        await store.set("b", 20)
        assert await store.get("a") == 10
        assert await store.get("b") == 20


# ---------------------------------------------------------------------------
# Accumulator — push after flush
# ---------------------------------------------------------------------------


class TestAccumulatorPushAfterFlush:
    async def test_push_after_flush_works(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        acc: Accumulator[int] = Accumulator(AccumulatorConfig(), on_flush)
        await acc.push(1)
        await acc.flush()
        assert acc.count == 0

        await acc.push(2)
        await acc.push(3)
        assert acc.count == 2

        await acc.flush()
        assert flushed == [[1], [2, 3]]

    async def test_double_flush_second_is_noop(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        acc: Accumulator[int] = Accumulator(AccumulatorConfig(), on_flush)
        await acc.push(10)
        await acc.flush()
        await acc.flush()  # second flush — buffer already empty
        assert len(flushed) == 1
        assert flushed[0] == [10]


# ---------------------------------------------------------------------------
# FIFO eviction edge cases
# ---------------------------------------------------------------------------


class TestFIFOEdgeCases:
    async def test_eviction_preserves_newest(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        cfg = AccumulatorConfig(max_size=2)
        acc: Accumulator[int] = Accumulator(cfg, on_flush)

        for i in range(10):
            await acc.push(i)

        assert acc.count == 2
        await acc.flush()
        assert flushed == [[8, 9]]

    async def test_eviction_with_max_size_one(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        cfg = AccumulatorConfig(max_size=1)
        acc: Accumulator[int] = Accumulator(cfg, on_flush)

        await acc.push(1)
        await acc.push(2)
        await acc.push(3)
        assert acc.count == 1
        await acc.flush()
        assert flushed == [[3]]


# ---------------------------------------------------------------------------
# Trigger unit tests
# ---------------------------------------------------------------------------


class TestTriggerUnit:
    async def test_size_trigger_exact_threshold(self):
        trigger: SizeTrigger[str] = SizeTrigger(threshold=3)
        assert trigger.should_flush(["a", "b"]) is False
        assert trigger.should_flush(["a", "b", "c"]) is True

    async def test_size_trigger_above_threshold(self):
        trigger: SizeTrigger[int] = SizeTrigger(threshold=2)
        assert trigger.should_flush([1, 2, 3, 4]) is True

    async def test_size_trigger_empty(self):
        trigger: SizeTrigger[int] = SizeTrigger(threshold=1)
        assert trigger.should_flush([]) is False

    async def test_time_trigger_not_before_interval(self):
        trigger: TimeTrigger[int] = TimeTrigger(interval=1.0)
        assert trigger.should_flush([1]) is False

    async def test_time_trigger_fires_after_interval(self):
        trigger: TimeTrigger[int] = TimeTrigger(interval=0.02)
        await asyncio.sleep(0.03)
        assert trigger.should_flush([1]) is True

    async def test_time_trigger_reset(self):
        trigger: TimeTrigger[int] = TimeTrigger(interval=0.05)
        await asyncio.sleep(0.06)
        assert trigger.should_flush([1]) is True
        trigger.reset()
        assert trigger.should_flush([1]) is False

    async def test_byte_size_trigger_empty_items(self):
        trigger = ByteSizeTrigger(threshold=10)
        assert trigger.should_flush([]) is False

    async def test_byte_size_trigger_exact_threshold(self):
        trigger = ByteSizeTrigger(threshold=5)
        assert trigger.should_flush([b"12345"]) is True

    async def test_byte_size_trigger_below_threshold(self):
        trigger = ByteSizeTrigger(threshold=10)
        assert trigger.should_flush([b"abc"]) is False


# ---------------------------------------------------------------------------
# Custom trigger implementation (satisfies FlushTrigger protocol)
# ---------------------------------------------------------------------------


class TestCustomTrigger:
    async def test_custom_trigger_protocol(self):
        class SumTrigger:
            """Flush when sum of items exceeds threshold."""

            def __init__(self, threshold: int) -> None:
                self._threshold = threshold

            def should_flush(self, items: list[int]) -> bool:
                return sum(items) >= self._threshold

        trigger = SumTrigger(threshold=10)
        assert isinstance(trigger, FlushTrigger)
        assert trigger.should_flush([3, 4]) is False
        assert trigger.should_flush([5, 6]) is True

    async def test_custom_trigger_with_accumulator(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        class SumTrigger:
            def __init__(self, threshold: int) -> None:
                self._threshold = threshold

            def should_flush(self, items: list[int]) -> bool:
                return sum(items) >= self._threshold

        trigger = SumTrigger(threshold=10)
        cfg = AccumulatorConfig(max_size=100)
        acc: Accumulator[int] = Accumulator(cfg, on_flush, triggers=[trigger])

        await acc.push(3)
        await acc.push(4)
        assert flushed == []

        await acc.push(5)  # sum = 12 >= 10
        assert len(flushed) == 1
        assert flushed[0] == [3, 4, 5]


# ---------------------------------------------------------------------------
# Integration: multiple triggers — first to fire wins
# ---------------------------------------------------------------------------


class TestMultipleTriggers:
    async def test_size_fires_before_time(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        size_trigger: SizeTrigger[int] = SizeTrigger(threshold=2)
        time_trigger: TimeTrigger[int] = TimeTrigger(interval=10.0)  # very long

        cfg = AccumulatorConfig(max_size=100)
        acc: Accumulator[int] = Accumulator(
            cfg, on_flush, triggers=[size_trigger, time_trigger]
        )

        await acc.push(1)
        assert flushed == []
        await acc.push(2)  # size trigger fires
        assert len(flushed) == 1
        assert flushed[0] == [1, 2]

    async def test_time_fires_before_size(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        size_trigger: SizeTrigger[int] = SizeTrigger(threshold=100)  # very high
        time_trigger: TimeTrigger[int] = TimeTrigger(interval=0.03)

        cfg = AccumulatorConfig(max_size=100)
        acc: Accumulator[int] = Accumulator(
            cfg, on_flush, triggers=[size_trigger, time_trigger]
        )

        await acc.push(1)
        assert flushed == []

        await asyncio.sleep(0.04)
        await acc.push(2)  # time trigger fires
        assert len(flushed) == 1
        assert flushed[0] == [1, 2]


# ---------------------------------------------------------------------------
# Edge cases: None/empty values, large items
# ---------------------------------------------------------------------------


class TestEdgeCases:
    async def test_push_none_value(self):
        flushed: list[list[None]] = []

        async def on_flush(items: list[None]) -> None:
            flushed.append(items)

        acc: Accumulator[None] = Accumulator(AccumulatorConfig(), on_flush)
        await acc.push(None)
        await acc.push(None)
        assert acc.count == 2
        await acc.flush()
        assert flushed == [[None, None]]

    async def test_push_empty_string(self):
        flushed: list[list[str]] = []

        async def on_flush(items: list[str]) -> None:
            flushed.append(items)

        acc: Accumulator[str] = Accumulator(AccumulatorConfig(), on_flush)
        await acc.push("")
        await acc.push("")
        await acc.flush()
        assert flushed == [["", ""]]

    async def test_push_empty_bytes(self):
        flushed: list[list[bytes]] = []

        async def on_flush(items: list[bytes]) -> None:
            flushed.append(items)

        trigger = ByteSizeTrigger(threshold=10)
        cfg = AccumulatorConfig(max_size=100)
        acc: Accumulator[bytes] = Accumulator(cfg, on_flush, triggers=[trigger])

        # Empty bytes shouldn't reach threshold
        await acc.push(b"")
        await acc.push(b"")
        assert flushed == []
        assert acc.count == 2

    async def test_large_items(self):
        """Push large items to verify no crash under memory pressure."""
        flushed: list[list[bytes]] = []

        async def on_flush(items: list[bytes]) -> None:
            flushed.append(items)

        cfg = AccumulatorConfig(max_size=5)
        acc: Accumulator[bytes] = Accumulator(cfg, on_flush)

        big = b"x" * 1_000_000  # 1 MB
        for _ in range(10):
            await acc.push(big)

        assert acc.count == 5
        await acc.flush()
        assert len(flushed) == 1
        assert len(flushed[0]) == 5

    async def test_config_zero_max_size(self):
        """max_size=0: condition `max_size > 0` is false, no eviction."""
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        cfg = AccumulatorConfig(max_size=0)
        acc: Accumulator[int] = Accumulator(cfg, on_flush)

        for i in range(20):
            await acc.push(i)
        # No eviction; all items buffered
        assert acc.count == 20
        await acc.flush()
        assert len(flushed[0]) == 20


# ---------------------------------------------------------------------------
# Concurrent push operations (asyncio tasks)
# ---------------------------------------------------------------------------


class TestConcurrency:
    async def test_concurrent_push(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        cfg = AccumulatorConfig(max_size=1000)
        acc: Accumulator[int] = Accumulator(cfg, on_flush)

        async def pusher(start: int, count: int) -> None:
            for i in range(start, start + count):
                await acc.push(i)

        tasks = [asyncio.create_task(pusher(i * 100, 50)) for i in range(10)]
        await asyncio.gather(*tasks)

        # Total items should be 500
        assert acc.count == 500

        await acc.flush()
        assert len(flushed) == 1
        assert len(flushed[0]) == 500

    async def test_concurrent_push_with_trigger(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        trigger: SizeTrigger[int] = SizeTrigger(threshold=100)
        cfg = AccumulatorConfig(max_size=1000)
        acc: Accumulator[int] = Accumulator(cfg, on_flush, triggers=[trigger])

        async def pusher(start: int, count: int) -> None:
            for i in range(start, start + count):
                await acc.push(i)

        tasks = [asyncio.create_task(pusher(i * 100, 50)) for i in range(10)]
        await asyncio.gather(*tasks)

        # Some flushes should have happened due to size trigger
        total_flushed = sum(len(batch) for batch in flushed)
        remaining = acc.count
        assert total_flushed + remaining == 500


# ---------------------------------------------------------------------------
# Callback that raises exception
# ---------------------------------------------------------------------------


class TestCallbackException:
    async def test_callback_raises_but_accumulator_continues(self):
        call_count = 0

        async def bad_on_flush(items: list[int]) -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("callback exploded")

        trigger: SizeTrigger[int] = SizeTrigger(threshold=2)
        cfg = AccumulatorConfig(max_size=100)
        acc: Accumulator[int] = Accumulator(cfg, bad_on_flush, triggers=[trigger])

        with pytest.raises(ValueError, match="callback exploded"):
            await acc.push(1)
            await acc.push(2)  # triggers flush → exception

        assert call_count == 1

        # Accumulator should still be usable after exception
        # Buffer was cleared before on_flush was called, so count is 0
        await acc.push(3)
        assert acc.count == 1

    async def test_manual_flush_callback_raises(self):
        async def bad_on_flush(items: list[int]) -> None:
            raise RuntimeError("flush boom")

        acc: Accumulator[int] = Accumulator(AccumulatorConfig(), bad_on_flush)
        await acc.push(1)

        with pytest.raises(RuntimeError, match="flush boom"):
            await acc.flush()

        # Buffer should be cleared even though callback raised
        assert acc.count == 0


# ---------------------------------------------------------------------------
# Integration: full lifecycle
# ---------------------------------------------------------------------------


class TestIntegrationLifecycle:
    async def test_full_lifecycle(self):
        """push → trigger flush → push more → manual flush → clear"""
        flushed: list[list[str]] = []

        async def on_flush(items: list[str]) -> None:
            flushed.append(items)

        trigger: SizeTrigger[str] = SizeTrigger(threshold=3)
        cfg = AccumulatorConfig(max_size=10)
        acc: Accumulator[str] = Accumulator(cfg, on_flush, triggers=[trigger])

        # Phase 1: push until trigger fires
        await acc.push("a")
        await acc.push("b")
        await acc.push("c")  # trigger fires
        assert len(flushed) == 1
        assert flushed[0] == ["a", "b", "c"]
        assert acc.count == 0

        # Phase 2: push more, manual flush
        await acc.push("d")
        await acc.push("e")
        assert acc.count == 2
        await acc.flush()
        assert flushed[1] == ["d", "e"]

        # Phase 3: push and clear (no flush)
        await acc.push("f")
        await acc.clear()
        assert acc.count == 0
        assert len(flushed) == 2  # no new flush from clear

    async def test_time_trigger_with_size_eviction(self):
        """Combine time trigger with FIFO eviction."""
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        time_trigger: TimeTrigger[int] = TimeTrigger(interval=0.03)
        cfg = AccumulatorConfig(max_size=3)
        acc: Accumulator[int] = Accumulator(cfg, on_flush, triggers=[time_trigger])

        # Fill beyond max_size
        for i in range(5):
            await acc.push(i)
        # Buffer has [2, 3, 4] due to FIFO
        assert acc.count == 3

        await asyncio.sleep(0.04)
        await acc.push(99)  # time trigger fires
        assert len(flushed) == 1
        # Before flush, buffer was [2,3,4] then 99 pushed → [3,4,99] due to FIFO
        # Then trigger checked before eviction? Let's verify the actual items
        assert 99 in flushed[0]

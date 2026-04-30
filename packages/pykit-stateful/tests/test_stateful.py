# mypy: ignore-errors
"""Tests for pykit-stateful: MemoryStore, Accumulator, triggers."""

from __future__ import annotations

import asyncio

from pykit_stateful import (
    Accumulator,
    AccumulatorConfig,
    ByteSizeTrigger,
    MemoryStore,
    SizeTrigger,
    TimeTrigger,
)

# ---------------------------------------------------------------------------
# MemoryStore CRUD
# ---------------------------------------------------------------------------


class TestMemoryStore:
    async def test_get_returns_none_for_missing_key(self):
        store: MemoryStore[str] = MemoryStore()
        assert await store.get("missing") is None

    async def test_set_and_get(self):
        store: MemoryStore[int] = MemoryStore()
        await store.set("a", 42)
        assert await store.get("a") == 42

    async def test_overwrite(self):
        store: MemoryStore[str] = MemoryStore()
        await store.set("k", "v1")
        await store.set("k", "v2")
        assert await store.get("k") == "v2"

    async def test_delete(self):
        store: MemoryStore[str] = MemoryStore()
        await store.set("k", "v")
        await store.delete("k")
        assert await store.get("k") is None

    async def test_delete_missing_key_is_noop(self):
        store: MemoryStore[str] = MemoryStore()
        await store.delete("nope")  # should not raise

    async def test_keys(self):
        store: MemoryStore[int] = MemoryStore()
        await store.set("a", 1)
        await store.set("b", 2)
        keys = await store.keys()
        assert sorted(keys) == ["a", "b"]

    async def test_keys_empty(self):
        store: MemoryStore[int] = MemoryStore()
        assert await store.keys() == []


# ---------------------------------------------------------------------------
# Accumulator — basic push / flush
# ---------------------------------------------------------------------------


class TestAccumulatorBasic:
    async def test_push_and_count(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        acc: Accumulator[int] = Accumulator(AccumulatorConfig(), on_flush)
        await acc.push(1)
        await acc.push(2)
        assert acc.count == 2
        assert flushed == []

    async def test_manual_flush(self):
        flushed: list[list[str]] = []

        async def on_flush(items: list[str]) -> None:
            flushed.append(items)

        acc: Accumulator[str] = Accumulator(AccumulatorConfig(), on_flush)
        await acc.push("a")
        await acc.push("b")
        await acc.flush()
        assert acc.count == 0
        assert flushed == [["a", "b"]]

    async def test_empty_flush_is_noop(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        acc: Accumulator[int] = Accumulator(AccumulatorConfig(), on_flush)
        await acc.flush()
        assert flushed == []

    async def test_clear(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        acc: Accumulator[int] = Accumulator(AccumulatorConfig(), on_flush)
        await acc.push(1)
        await acc.push(2)
        await acc.clear()
        assert acc.count == 0
        assert flushed == []


# ---------------------------------------------------------------------------
# Accumulator — FIFO eviction
# ---------------------------------------------------------------------------


class TestAccumulatorFIFO:
    async def test_fifo_eviction(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        cfg = AccumulatorConfig(max_size=3)
        acc: Accumulator[int] = Accumulator(cfg, on_flush)
        for i in range(5):
            await acc.push(i)
        # Buffer should contain [2, 3, 4] — oldest items evicted
        assert acc.count == 3
        await acc.flush()
        assert flushed == [[2, 3, 4]]


# ---------------------------------------------------------------------------
# Accumulator — SizeTrigger
# ---------------------------------------------------------------------------


class TestSizeTrigger:
    async def test_auto_flush_on_size(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        trigger: SizeTrigger[int] = SizeTrigger(threshold=3)
        cfg = AccumulatorConfig(max_size=100)
        acc: Accumulator[int] = Accumulator(cfg, on_flush, triggers=[trigger])

        await acc.push(1)
        await acc.push(2)
        assert flushed == []
        await acc.push(3)
        # Trigger fires at count >= 3
        assert len(flushed) == 1
        assert flushed[0] == [1, 2, 3]
        assert acc.count == 0

    async def test_size_trigger_should_flush(self):
        trigger: SizeTrigger[int] = SizeTrigger(threshold=2)
        assert trigger.should_flush([1]) is False
        assert trigger.should_flush([1, 2]) is True
        assert trigger.should_flush([1, 2, 3]) is True


# ---------------------------------------------------------------------------
# Accumulator — ByteSizeTrigger
# ---------------------------------------------------------------------------


class TestByteSizeTrigger:
    async def test_byte_size_trigger(self):
        flushed: list[list[bytes]] = []

        async def on_flush(items: list[bytes]) -> None:
            flushed.append(items)

        trigger = ByteSizeTrigger(threshold=10)
        cfg = AccumulatorConfig(max_size=100)
        acc: Accumulator[bytes] = Accumulator(cfg, on_flush, triggers=[trigger])

        await acc.push(b"hello")  # 5 bytes
        assert flushed == []
        await acc.push(b"world")  # 5 more = 10 total
        assert len(flushed) == 1
        assert flushed[0] == [b"hello", b"world"]

    async def test_custom_measurer(self):
        trigger = ByteSizeTrigger(threshold=6, measurer=lambda b: len(b) * 2)
        assert trigger.should_flush([b"abc"]) is True  # 3*2 = 6 >= 6
        assert trigger.should_flush([b"ab"]) is False  # 2*2 = 4 < 6


# ---------------------------------------------------------------------------
# Accumulator — TimeTrigger
# ---------------------------------------------------------------------------


class TestTimeTrigger:
    async def test_time_trigger_fires(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        trigger: TimeTrigger[int] = TimeTrigger(interval=0.05)
        cfg = AccumulatorConfig(max_size=100)
        acc: Accumulator[int] = Accumulator(cfg, on_flush, triggers=[trigger])

        await acc.push(1)
        assert flushed == []

        await asyncio.sleep(0.06)
        await acc.push(2)
        # Time trigger should fire after interval
        assert len(flushed) == 1
        assert flushed[0] == [1, 2]

    async def test_time_trigger_resets_after_flush(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        trigger: TimeTrigger[int] = TimeTrigger(interval=0.05)
        cfg = AccumulatorConfig(max_size=100)
        acc: Accumulator[int] = Accumulator(cfg, on_flush, triggers=[trigger])

        await asyncio.sleep(0.06)
        await acc.push(1)  # triggers flush
        assert len(flushed) == 1

        # Timer resets — pushing immediately should not trigger
        await acc.push(2)
        assert len(flushed) == 1
        assert acc.count == 1


# ---------------------------------------------------------------------------
# Accumulator — flush_interval config shortcut
# ---------------------------------------------------------------------------


class TestFlushIntervalConfig:
    async def test_flush_interval_creates_time_trigger(self):
        flushed: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            flushed.append(items)

        cfg = AccumulatorConfig(flush_interval=0.05)
        acc: Accumulator[int] = Accumulator(cfg, on_flush)

        await acc.push(1)
        assert flushed == []

        await asyncio.sleep(0.06)
        await acc.push(2)
        assert len(flushed) == 1


# ---------------------------------------------------------------------------
# Accumulator — on_flush callback
# ---------------------------------------------------------------------------


class TestOnFlushCallback:
    async def test_callback_receives_items(self):
        received: list[list[str]] = []

        async def on_flush(items: list[str]) -> None:
            received.append(list(items))

        cfg = AccumulatorConfig()
        trigger: SizeTrigger[str] = SizeTrigger(threshold=2)
        acc: Accumulator[str] = Accumulator(cfg, on_flush, triggers=[trigger])

        await acc.push("x")
        await acc.push("y")
        assert received == [["x", "y"]]

    async def test_multiple_flushes(self):
        received: list[list[int]] = []

        async def on_flush(items: list[int]) -> None:
            received.append(items)

        trigger: SizeTrigger[int] = SizeTrigger(threshold=2)
        cfg = AccumulatorConfig(max_size=100)
        acc: Accumulator[int] = Accumulator(cfg, on_flush, triggers=[trigger])

        await acc.push(1)
        await acc.push(2)  # flush
        await acc.push(3)
        await acc.push(4)  # flush
        assert received == [[1, 2], [3, 4]]

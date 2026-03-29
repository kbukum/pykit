"""pykit_stateful — Stateful accumulator with flush triggers."""

from __future__ import annotations

from pykit_stateful.accumulator import Accumulator, AccumulatorConfig
from pykit_stateful.store import MemoryStore, Store
from pykit_stateful.trigger import ByteSizeTrigger, FlushTrigger, SizeTrigger, TimeTrigger

__all__ = [
    "Accumulator",
    "AccumulatorConfig",
    "ByteSizeTrigger",
    "FlushTrigger",
    "MemoryStore",
    "SizeTrigger",
    "Store",
    "TimeTrigger",
]

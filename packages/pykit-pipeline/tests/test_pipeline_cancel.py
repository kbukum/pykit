"""Cancellation regression tests for background pipeline operators."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

import pytest

from pykit_pipeline import Pipeline, PipelineIterator


class SlowIterator(PipelineIterator[int]):
    """Iterator that yields a finite sequence slowly enough to close mid-stream."""

    def __init__(self, delay: float = 0.01, limit: int = 100) -> None:
        self._delay = delay
        self._limit = limit
        self._value = 0
        self.closed = False

    async def next(self) -> int | None:
        if self._value >= self._limit:
            return None
        await asyncio.sleep(self._delay)
        self._value += 1
        return self._value

    async def close(self) -> None:
        self.closed = True


async def _assert_close_does_not_surface_cancelled_error(pipeline: Pipeline[int]) -> None:
    iterator = pipeline.iter()
    await iterator.next()
    try:
        await iterator.close()
    except asyncio.CancelledError as exc:  # pragma: no cover - assertion path
        raise AssertionError("pipeline close surfaced CancelledError") from exc


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "build",
    [
        lambda source: source.parallel(2, lambda value: value),
        lambda source: source.merge(Pipeline.from_fn(SlowIterator)),
        lambda source: source.debounce(0.001),
        lambda source: source.buffer(1),
    ],
)
async def test_background_operator_close_preserves_cancelled_error_semantics(
    build: Callable[[Pipeline[int]], Pipeline[int]],
) -> None:
    source = Pipeline.from_fn(SlowIterator)
    await _assert_close_does_not_surface_cancelled_error(build(source))

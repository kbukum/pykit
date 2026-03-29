"""Core pipeline types, constructors, operators, and terminals."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

T = TypeVar("T")
U = TypeVar("U")
R = TypeVar("R")


class PipelineIterator[T](AsyncIterator[T]):
    """Async iterator providing pull-based sequential access to values.

    Mirrors gokit's ``pipeline.Iterator[T]``.
    """

    @abstractmethod
    async def next(self) -> T | None:
        """Return the next value, or ``None`` when exhausted."""
        ...

    async def close(self) -> None:
        """Release any resources held by the iterator."""

    def __aiter__(self) -> PipelineIterator[T]:
        return self

    async def __anext__(self) -> T:
        val = await self.next()
        if val is None:
            raise StopAsyncIteration
        return val


class Pipeline[T]:
    """A lazy, pull-based async data pipeline.

    No work happens until values are pulled via :func:`collect`,
    :func:`drain`, or :func:`for_each`.

    Example::

        src = Pipeline.from_list([1, 2, 3, 4, 5])
        doubled = src.map(lambda x: x * 2)
        evens = doubled.filter(lambda x: x % 2 == 0)
        results = await collect(evens)
    """

    def __init__(self, create: Callable[[], PipelineIterator[T]]) -> None:
        self._create = create

    @classmethod
    def from_list(cls, items: list[T]) -> Pipeline[T]:
        """Create a pipeline from a list of values."""
        return cls(lambda: _SliceIter(list(items)))

    @classmethod
    def from_fn(cls, factory: Callable[[], PipelineIterator[T]]) -> Pipeline[T]:
        """Create a pipeline from a factory that produces an iterator."""
        return cls(factory)

    @classmethod
    def from_iter(cls, iterator: PipelineIterator[T]) -> Pipeline[T]:
        """Create a pipeline from an existing iterator (consumed once)."""
        taken: list[PipelineIterator[T] | None] = [iterator]

        def _factory() -> PipelineIterator[T]:
            it = taken[0]
            taken[0] = None
            if it is None:
                return _EmptyIter()
            return it

        return cls(_factory)

    def iter(self) -> PipelineIterator[T]:
        """Return the raw iterator. Caller manages its lifecycle."""
        return self._create()

    def map(self, fn: Callable[[T], U]) -> Pipeline[U]:
        """Transform each value using a function."""
        create = self._create
        return Pipeline(lambda: _MapIter(create(), fn))

    def filter(self, predicate: Callable[[T], bool]) -> Pipeline[T]:
        """Keep only values that satisfy the predicate."""
        create = self._create
        return Pipeline(lambda: _FilterIter(create(), predicate))

    def tap(self, fn: Callable[[T], None]) -> Pipeline[T]:
        """Call a function as a side-effect for each value, passing it through unchanged."""
        create = self._create
        return Pipeline(lambda: _TapIter(create(), fn))

    def flat_map(self, fn: Callable[[T], PipelineIterator[U]]) -> Pipeline[U]:
        """Transform each value into an iterator and flatten the results."""
        create = self._create
        return Pipeline(lambda: _FlatMapIter(create(), fn))


# --- Terminals ---


async def collect[T](pipeline: Pipeline[T]) -> list[T]:
    """Collect all values from a pipeline into a list."""
    it = pipeline.iter()
    result: list[T] = []
    try:
        while True:
            val = await it.next()
            if val is None:
                return result
            result.append(val)
    finally:
        await it.close()


async def drain[T](pipeline: Pipeline[T], sink: Callable[[T], None | Awaitable[None]]) -> None:
    """Pull all values from a pipeline and send each to a sink function."""
    import asyncio

    it = pipeline.iter()
    try:
        while True:
            val = await it.next()
            if val is None:
                return
            result = sink(val)
            if asyncio.iscoroutine(result) or asyncio.isfuture(result):
                await result
    finally:
        await it.close()


async def for_each[T](pipeline: Pipeline[T], fn: Callable[[T], None | Awaitable[None]]) -> None:
    """Pull all values and call a function for each."""
    await drain(pipeline, fn)


def concat[T](*pipelines: Pipeline[T]) -> Pipeline[T]:
    """Join multiple pipelines sequentially."""
    creators = [p._create for p in pipelines]
    return Pipeline(lambda: _ConcatIter([c() for c in creators]))


def reduce[T, R](pipeline: Pipeline[T], init: R, fn: Callable[[R, T], R]) -> Pipeline[R]:
    """Accumulate all values into a single result."""
    create = pipeline._create
    return Pipeline(lambda: _ReduceIter(create(), init, fn))


# --- Internal iterator implementations ---


class _SliceIter(PipelineIterator[T]):
    def __init__(self, items: list[T]) -> None:
        self._items = items
        self._index = 0

    async def next(self) -> T | None:
        if self._index >= len(self._items):
            return None
        val = self._items[self._index]
        self._index += 1
        return val


class _EmptyIter(PipelineIterator[T]):
    async def next(self) -> T | None:
        return None


class _MapIter[T, U](PipelineIterator[U]):
    def __init__(self, source: PipelineIterator[T], fn: Callable[[T], U]) -> None:
        self._source = source
        self._fn = fn

    async def next(self) -> U | None:
        val = await self._source.next()
        if val is None:
            return None
        return self._fn(val)

    async def close(self) -> None:
        await self._source.close()


class _FilterIter(PipelineIterator[T]):
    def __init__(self, source: PipelineIterator[T], predicate: Callable[[T], bool]) -> None:
        self._source = source
        self._predicate = predicate

    async def next(self) -> T | None:
        while True:
            val = await self._source.next()
            if val is None:
                return None
            if self._predicate(val):
                return val

    async def close(self) -> None:
        await self._source.close()


class _TapIter(PipelineIterator[T]):
    def __init__(self, source: PipelineIterator[T], fn: Callable[[T], None]) -> None:
        self._source = source
        self._fn = fn

    async def next(self) -> T | None:
        val = await self._source.next()
        if val is None:
            return None
        self._fn(val)
        return val

    async def close(self) -> None:
        await self._source.close()


class _FlatMapIter[T, U](PipelineIterator[U]):
    def __init__(self, source: PipelineIterator[T], fn: Callable[[T], PipelineIterator[U]]) -> None:
        self._source = source
        self._fn = fn
        self._current: PipelineIterator[U] | None = None

    async def next(self) -> U | None:
        while True:
            if self._current is not None:
                val = await self._current.next()
                if val is not None:
                    return val
                await self._current.close()
                self._current = None

            source_val = await self._source.next()
            if source_val is None:
                return None
            self._current = self._fn(source_val)

    async def close(self) -> None:
        if self._current is not None:
            await self._current.close()
        await self._source.close()


class _ConcatIter(PipelineIterator[T]):
    def __init__(self, iters: list[PipelineIterator[T]]) -> None:
        self._iters = iters
        self._index = 0

    async def next(self) -> T | None:
        while self._index < len(self._iters):
            val = await self._iters[self._index].next()
            if val is not None:
                return val
            self._index += 1
        return None

    async def close(self) -> None:
        for it in self._iters:
            await it.close()


class _ReduceIter[T, R](PipelineIterator[R]):
    def __init__(self, source: PipelineIterator[T], init: R, fn: Callable[[R, T], R]) -> None:
        self._source = source
        self._acc = init
        self._fn = fn
        self._done = False

    async def next(self) -> R | None:
        if self._done:
            return None
        while True:
            val = await self._source.next()
            if val is None:
                self._done = True
                return self._acc
            self._acc = self._fn(self._acc, val)

    async def close(self) -> None:
        await self._source.close()

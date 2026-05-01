"""Core pipeline types, constructors, operators, and terminals."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import time
from abc import abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import cast


class PipelineIterator[T](AsyncIterator[T]):
    """Async iterator providing pull-based sequential access to values."""

    @abstractmethod
    async def next(self) -> T | None:
        """Return the next value, or ``None`` when exhausted."""

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
    """A lazy, pull-based async data pipeline."""

    def __init__(self, create: Callable[[], PipelineIterator[T]]) -> None:
        self._create = create

    @classmethod
    def from_list(cls, items: Iterable[T]) -> Pipeline[T]:
        """Create a pipeline from an iterable of values."""
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

    def map[U](self, fn: Callable[[T], U]) -> Pipeline[U]:
        """Transform each value using a function."""
        create = self._create
        return Pipeline(lambda: _MapIter(create(), fn))

    def filter(self, predicate: Callable[[T], bool]) -> Pipeline[T]:
        """Keep only values that satisfy the predicate."""
        create = self._create
        return Pipeline(lambda: _FilterIter(create(), predicate))

    def tap(self, fn: Callable[[T], None]) -> Pipeline[T]:
        """Call a function for each value, passing it through unchanged."""
        create = self._create
        return Pipeline(lambda: _TapIter(create(), fn))

    def flat_map[U](self, fn: Callable[[T], PipelineIterator[U]]) -> Pipeline[U]:
        """Transform each value into an iterator and flatten the results."""
        create = self._create
        return Pipeline(lambda: _FlatMapIter(create(), fn))

    def batch(self, size: int) -> Pipeline[list[T]]:
        """Group values into fixed-size batches."""
        create = self._create
        return Pipeline(lambda: _BatchIter(create(), size))

    def tumbling_window(self, size: int) -> Pipeline[list[T]]:
        """Group values into non-overlapping count-based windows."""
        return self.batch(size)

    def sliding_window(self, size: int, step: int = 1) -> Pipeline[list[T]]:
        """Emit overlapping count-based windows."""
        create = self._create
        return Pipeline(lambda: _SlidingWindowIter(create(), size, step))

    def parallel[U](
        self,
        concurrency: int,
        fn: Callable[[T], U | Awaitable[U]],
    ) -> Pipeline[U]:
        """Apply *fn* concurrently to values. Order is not preserved."""
        concurrency = max(concurrency, 1)
        create = self._create

        def _factory() -> PipelineIterator[U]:
            source = create()
            input_queue: asyncio.Queue[T | None] = asyncio.Queue(maxsize=concurrency)
            output_queue: asyncio.Queue[_QueueMessage[U]] = asyncio.Queue(maxsize=concurrency)
            stop_event = asyncio.Event()

            async def produce() -> None:
                try:
                    while not stop_event.is_set():
                        value = await source.next()
                        if value is None:
                            break
                        await input_queue.put(value)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    await _put_safely(output_queue, _QueueMessage(error=exc))
                    stop_event.set()
                finally:
                    for _ in range(concurrency):
                        if stop_event.is_set():
                            with contextlib.suppress(asyncio.QueueFull):
                                input_queue.put_nowait(None)
                        else:
                            await input_queue.put(None)

            async def worker() -> None:
                try:
                    while True:
                        value = await input_queue.get()
                        if value is None:
                            return
                        result = await _resolve_value(fn(value))
                        await output_queue.put(_QueueMessage(value=result))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if not stop_event.is_set():
                        stop_event.set()
                        await _put_safely(output_queue, _QueueMessage(error=exc))
                finally:
                    done_message = _QueueMessage[U](done=True)
                    if stop_event.is_set():
                        with contextlib.suppress(asyncio.QueueFull):
                            output_queue.put_nowait(done_message)
                    else:
                        await _put_safely(output_queue, done_message)

            producer = asyncio.create_task(produce())
            workers = [asyncio.create_task(worker()) for _ in range(concurrency)]
            return _QueueIter(
                output_queue,
                workers,
                lambda: _close_background(source, stop_event, producer, workers),
            )

        return Pipeline(_factory)

    def merge(self, *others: Pipeline[T]) -> Pipeline[T]:
        """Combine multiple pipelines concurrently. Order is not preserved."""
        pipelines = (self, *others)

        def _factory() -> PipelineIterator[T]:
            iterators = [pipeline.iter() for pipeline in pipelines]
            output_queue: asyncio.Queue[_QueueMessage[T]] = asyncio.Queue(maxsize=max(len(iterators), 1))
            stop_event = asyncio.Event()

            async def forward(iterator: PipelineIterator[T]) -> None:
                try:
                    while not stop_event.is_set():
                        value = await iterator.next()
                        if value is None:
                            return
                        await output_queue.put(_QueueMessage(value=value))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    if not stop_event.is_set():
                        stop_event.set()
                        await _put_safely(output_queue, _QueueMessage(error=exc))
                finally:
                    done_message = _QueueMessage[T](done=True)
                    if stop_event.is_set():
                        with contextlib.suppress(asyncio.QueueFull):
                            output_queue.put_nowait(done_message)
                    else:
                        await _put_safely(output_queue, done_message)

            tasks = [asyncio.create_task(forward(iterator)) for iterator in iterators]
            return _QueueIter(
                output_queue,
                tasks,
                lambda: _close_merge(iterators, stop_event, tasks),
            )

        return Pipeline(_factory)

    def fan_out[U](self, *fns: Callable[[T], U | Awaitable[U]]) -> Pipeline[list[U]]:
        """Apply multiple functions to each value concurrently."""
        create = self._create
        return Pipeline(lambda: _FanOutIter(create(), fns))

    def throttle(self, interval: float) -> Pipeline[T]:
        """Drop values that arrive faster than *interval* seconds."""
        if interval <= 0:
            return self
        create = self._create
        return Pipeline(lambda: _ThrottleIter(create(), interval))

    def debounce(self, interval: float) -> Pipeline[T]:
        """Emit only the latest value after *interval* seconds of silence."""
        if interval <= 0:
            return self
        create = self._create

        def _factory() -> PipelineIterator[T]:
            source = create()
            queue: asyncio.Queue[_QueueMessage[T]] = asyncio.Queue(maxsize=1)
            stop_event = asyncio.Event()

            async def produce() -> None:
                try:
                    while not stop_event.is_set():
                        value = await source.next()
                        if value is None:
                            break
                        await queue.put(_QueueMessage(value=value))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    await _put_safely(queue, _QueueMessage(error=exc))
                finally:
                    done_message = _QueueMessage[T](done=True)
                    if stop_event.is_set():
                        with contextlib.suppress(asyncio.QueueFull):
                            queue.put_nowait(done_message)
                    else:
                        await _put_safely(queue, done_message)

            producer = asyncio.create_task(produce())
            return _DebounceIter(
                queue,
                interval,
                lambda: _close_background(source, stop_event, producer, []),
            )

        return Pipeline(_factory)

    def distinct(self) -> Pipeline[T]:
        """Emit only the first occurrence of each value."""
        create = self._create
        return Pipeline(lambda: _DistinctIter(create()))

    def take(self, n: int) -> Pipeline[T]:
        """Emit at most *n* values."""
        if n <= 0:
            return Pipeline(_EmptyIter)
        create = self._create
        return Pipeline(lambda: _TakeIter(create(), n))

    def skip(self, n: int) -> Pipeline[T]:
        """Skip the first *n* values."""
        if n <= 0:
            return self
        create = self._create
        return Pipeline(lambda: _SkipIter(create(), n))

    def partition(self, predicate: Callable[[T], bool]) -> tuple[Pipeline[T], Pipeline[T]]:
        """Split values into matching and non-matching pipelines."""
        state = _PartitionState(self._create, predicate)
        return (
            Pipeline(lambda: _PartitionIter(state, True)),
            Pipeline(lambda: _PartitionIter(state, False)),
        )

    def buffer(self, size: int) -> Pipeline[T]:
        """Insert an async buffer between producer and consumer."""
        size = max(size, 1)
        create = self._create

        def _factory() -> PipelineIterator[T]:
            source = create()
            queue: asyncio.Queue[_QueueMessage[T]] = asyncio.Queue(maxsize=size)
            stop_event = asyncio.Event()

            async def produce() -> None:
                try:
                    while not stop_event.is_set():
                        value = await source.next()
                        if value is None:
                            break
                        await queue.put(_QueueMessage(value=value))
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    await _put_safely(queue, _QueueMessage(error=exc))
                finally:
                    done_message = _QueueMessage[T](done=True)
                    if stop_event.is_set():
                        with contextlib.suppress(asyncio.QueueFull):
                            queue.put_nowait(done_message)
                    else:
                        await _put_safely(queue, done_message)

            producer = asyncio.create_task(produce())
            return _QueueIter(
                queue,
                [producer],
                lambda: _close_background(source, stop_event, producer, []),
            )

        return Pipeline(_factory)


async def collect[T](pipeline: Pipeline[T]) -> list[T]:
    """Collect all values from a pipeline into a list."""
    iterator = pipeline.iter()
    result: list[T] = []
    try:
        while True:
            value = await iterator.next()
            if value is None:
                return result
            result.append(value)
    finally:
        await iterator.close()


async def drain[T](pipeline: Pipeline[T], sink: Callable[[T], None | Awaitable[None]]) -> None:
    """Pull all values from a pipeline and send each to a sink function."""
    iterator = pipeline.iter()
    try:
        while True:
            value = await iterator.next()
            if value is None:
                return
            result = sink(value)
            if inspect.isawaitable(result):
                await result
    finally:
        await iterator.close()


async def for_each[T](pipeline: Pipeline[T], fn: Callable[[T], None | Awaitable[None]]) -> None:
    """Pull all values and call a function for each."""
    await drain(pipeline, fn)


def concat[T](*pipelines: Pipeline[T]) -> Pipeline[T]:
    """Join multiple pipelines sequentially."""
    creators = [pipeline._create for pipeline in pipelines]
    return Pipeline(lambda: _ConcatIter([creator() for creator in creators]))


def reduce[T, R](pipeline: Pipeline[T], init: R, fn: Callable[[R, T], R]) -> Pipeline[R]:
    """Accumulate all values into a single result."""
    create = pipeline._create
    return Pipeline(lambda: _ReduceIter(create(), init, fn))


@dataclass(slots=True)
class _QueueMessage[T]:
    value: T | None = None
    error: Exception | None = None
    done: bool = False


async def _resolve_value[T](value: T | Awaitable[T]) -> T:
    if inspect.isawaitable(value):
        return await value
    return value


async def _put_safely[T](queue: asyncio.Queue[_QueueMessage[T]], message: _QueueMessage[T]) -> None:
    try:
        await queue.put(message)
    except asyncio.CancelledError:
        # The iterator is closing; dropping the terminal queue message is safe.
        return


class _QueueIter[T](PipelineIterator[T]):
    def __init__(
        self,
        queue: asyncio.Queue[_QueueMessage[T]],
        tasks: list[asyncio.Task[None]],
        close_fn: Callable[[], Awaitable[None]],
    ) -> None:
        self._queue = queue
        self._tasks = tasks
        self._close_fn = close_fn
        self._done_messages_remaining = len(tasks)
        self._closed = False

    async def next(self) -> T | None:
        while self._done_messages_remaining > 0:
            message = await self._queue.get()
            if message.error is not None:
                raise message.error
            if message.done:
                self._done_messages_remaining -= 1
                continue
            return message.value
        return None

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._close_fn()


async def _close_background[T](
    source: PipelineIterator[T],
    stop_event: asyncio.Event,
    producer: asyncio.Task[None],
    workers: list[asyncio.Task[None]],
) -> None:
    stop_event.set()
    producer.cancel()
    for worker in workers:
        worker.cancel()
    await asyncio.gather(producer, *workers, return_exceptions=True)
    await source.close()


async def _close_merge[T](
    iterators: list[PipelineIterator[T]],
    stop_event: asyncio.Event,
    tasks: list[asyncio.Task[None]],
) -> None:
    stop_event.set()
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    for iterator in iterators:
        await iterator.close()


class _SliceIter[T](PipelineIterator[T]):
    def __init__(self, items: list[T]) -> None:
        self._items = items
        self._index = 0

    async def next(self) -> T | None:
        if self._index >= len(self._items):
            return None
        value = self._items[self._index]
        self._index += 1
        return value


class _EmptyIter[T](PipelineIterator[T]):
    async def next(self) -> T | None:
        return None


class _MapIter[T, U](PipelineIterator[U]):
    def __init__(self, source: PipelineIterator[T], fn: Callable[[T], U]) -> None:
        self._source = source
        self._fn = fn

    async def next(self) -> U | None:
        value = await self._source.next()
        if value is None:
            return None
        return self._fn(value)

    async def close(self) -> None:
        await self._source.close()


class _FilterIter[T](PipelineIterator[T]):
    def __init__(self, source: PipelineIterator[T], predicate: Callable[[T], bool]) -> None:
        self._source = source
        self._predicate = predicate

    async def next(self) -> T | None:
        while True:
            value = await self._source.next()
            if value is None:
                return None
            if self._predicate(value):
                return value

    async def close(self) -> None:
        await self._source.close()


class _TapIter[T](PipelineIterator[T]):
    def __init__(self, source: PipelineIterator[T], fn: Callable[[T], None]) -> None:
        self._source = source
        self._fn = fn

    async def next(self) -> T | None:
        value = await self._source.next()
        if value is None:
            return None
        self._fn(value)
        return value

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
                value = await self._current.next()
                if value is not None:
                    return value
                await self._current.close()
                self._current = None

            source_value = await self._source.next()
            if source_value is None:
                return None
            self._current = self._fn(source_value)

    async def close(self) -> None:
        if self._current is not None:
            await self._current.close()
        await self._source.close()


class _BatchIter[T](PipelineIterator[list[T]]):
    def __init__(self, source: PipelineIterator[T], size: int) -> None:
        self._source = source
        self._size = max(size, 1)

    async def next(self) -> list[T] | None:
        batch: list[T] = []
        while len(batch) < self._size:
            value = await self._source.next()
            if value is None:
                break
            batch.append(value)
        return batch or None

    async def close(self) -> None:
        await self._source.close()


class _SlidingWindowIter[T](PipelineIterator[list[T]]):
    def __init__(self, source: PipelineIterator[T], size: int, step: int) -> None:
        self._source = source
        self._size = max(size, 1)
        self._step = max(step, 1)
        self._buffer: list[T] = []
        self._done = False
        self._skip_remaining = 0

    async def next(self) -> list[T] | None:
        if self._done and len(self._buffer) < self._size:
            return None

        while len(self._buffer) < self._size and not self._done:
            value = await self._source.next()
            if value is None:
                self._done = True
                break
            if self._skip_remaining > 0:
                self._skip_remaining -= 1
                continue
            self._buffer.append(value)

        if len(self._buffer) < self._size:
            return None

        window = list(self._buffer[: self._size])
        drop_count = min(self._step, len(self._buffer))
        self._buffer = self._buffer[drop_count:]
        if self._step > drop_count:
            self._skip_remaining += self._step - drop_count
        return window

    async def close(self) -> None:
        await self._source.close()


class _FanOutIter[T, U](PipelineIterator[list[U]]):
    def __init__(
        self,
        source: PipelineIterator[T],
        fns: tuple[Callable[[T], U | Awaitable[U]], ...],
    ) -> None:
        self._source = source
        self._fns = fns

    async def next(self) -> list[U] | None:
        value = await self._source.next()
        if value is None:
            return None
        return list(await asyncio.gather(*(_resolve_value(fn(value)) for fn in self._fns)))

    async def close(self) -> None:
        await self._source.close()


class _ThrottleIter[T](PipelineIterator[T]):
    def __init__(self, source: PipelineIterator[T], interval: float) -> None:
        self._source = source
        self._interval = interval
        self._last_emit = 0.0

    async def next(self) -> T | None:
        while True:
            value = await self._source.next()
            if value is None:
                return None
            now = time.monotonic()
            if self._last_emit == 0.0 or now - self._last_emit >= self._interval:
                self._last_emit = now
                return value

    async def close(self) -> None:
        await self._source.close()


class _DebounceIter[T](PipelineIterator[T]):
    def __init__(
        self,
        queue: asyncio.Queue[_QueueMessage[T]],
        interval: float,
        close_fn: Callable[[], Awaitable[None]],
    ) -> None:
        self._queue = queue
        self._interval = interval
        self._close_fn = close_fn
        self._closed = False
        self._done = False

    async def next(self) -> T | None:
        if self._done:
            return None

        latest: T | None = None
        has_value = False
        timer_task: asyncio.Task[None] | None = None

        try:
            while True:
                queue_task = asyncio.create_task(self._queue.get())
                wait_tasks: set[asyncio.Task[object]] = {cast("asyncio.Task[object]", queue_task)}
                if has_value:
                    timer_task = asyncio.create_task(asyncio.sleep(self._interval))
                    wait_tasks.add(cast("asyncio.Task[object]", timer_task))
                done, pending = await asyncio.wait(wait_tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                if pending:
                    await asyncio.gather(*pending, return_exceptions=True)

                # asyncio.wait can complete multiple tasks in the same event-loop
                # tick (e.g., timer and queue both become ready simultaneously).
                # Check membership explicitly instead of done.pop() so we never
                # discard a queue message that was already dequeued.
                queue_fired = queue_task in done
                timer_fired = timer_task is not None and timer_task in done

                if timer_fired and not queue_fired:
                    # Debounce interval elapsed with no new message → emit.
                    return latest

                # A new message arrived (queue fired, possibly alongside the timer).
                # Process it; if the timer also fired we simply let it restart next
                # iteration — the new message resets the debounce window.
                message = queue_task.result()
                if message.error is not None:
                    raise message.error
                if message.done:
                    self._done = True
                    return latest if has_value else None
                latest = message.value
                has_value = True
        finally:
            if timer_task is not None:
                timer_task.cancel()
                await asyncio.gather(timer_task, return_exceptions=True)

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        await self._close_fn()


class _DistinctTracker[T]:
    def __init__(self) -> None:
        self._hashable_seen: set[object] = set()
        self._unhashable_seen: list[T] = []

    def accept(self, value: T) -> bool:
        try:
            marker = cast("object", value)
            if marker in self._hashable_seen:
                return False
            self._hashable_seen.add(marker)
            return True
        except TypeError:
            if value in self._unhashable_seen:
                return False
            self._unhashable_seen.append(value)
            return True


class _DistinctIter[T](PipelineIterator[T]):
    def __init__(self, source: PipelineIterator[T]) -> None:
        self._source = source
        self._tracker: _DistinctTracker[T] = _DistinctTracker()

    async def next(self) -> T | None:
        while True:
            value = await self._source.next()
            if value is None:
                return None
            if self._tracker.accept(value):
                return value

    async def close(self) -> None:
        await self._source.close()


class _TakeIter[T](PipelineIterator[T]):
    def __init__(self, source: PipelineIterator[T], limit: int) -> None:
        self._source = source
        self._remaining = limit

    async def next(self) -> T | None:
        if self._remaining <= 0:
            return None
        value = await self._source.next()
        if value is None:
            return None
        self._remaining -= 1
        return value

    async def close(self) -> None:
        await self._source.close()


class _SkipIter[T](PipelineIterator[T]):
    def __init__(self, source: PipelineIterator[T], count: int) -> None:
        self._source = source
        self._remaining = count

    async def next(self) -> T | None:
        while self._remaining > 0:
            value = await self._source.next()
            if value is None:
                return None
            self._remaining -= 1
        return await self._source.next()

    async def close(self) -> None:
        await self._source.close()


class _PartitionState[T]:
    def __init__(self, create: Callable[[], PipelineIterator[T]], predicate: Callable[[T], bool]) -> None:
        self._create = create
        self._predicate = predicate
        self._lock = asyncio.Lock()
        self._loaded = False
        self._matched: list[T] = []
        self._unmatched: list[T] = []

    async def values(self, matched: bool) -> list[T]:
        await self._ensure_loaded()
        return self._matched if matched else self._unmatched

    async def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        async with self._lock:
            if self._loaded:
                return
            source = self._create()
            try:
                while True:
                    value = await source.next()
                    if value is None:
                        break
                    if self._predicate(value):
                        self._matched.append(value)
                    else:
                        self._unmatched.append(value)
            finally:
                await source.close()
            self._loaded = True


class _PartitionIter[T](PipelineIterator[T]):
    def __init__(self, state: _PartitionState[T], matched: bool) -> None:
        self._state = state
        self._matched = matched
        self._values: list[T] | None = None
        self._index = 0

    async def next(self) -> T | None:
        if self._values is None:
            self._values = list(await self._state.values(self._matched))
        if self._index >= len(self._values):
            return None
        value = self._values[self._index]
        self._index += 1
        return value


class _ConcatIter[T](PipelineIterator[T]):
    def __init__(self, iters: list[PipelineIterator[T]]) -> None:
        self._iters = iters
        self._index = 0

    async def next(self) -> T | None:
        while self._index < len(self._iters):
            value = await self._iters[self._index].next()
            if value is not None:
                return value
            self._index += 1
        return None

    async def close(self) -> None:
        for iterator in self._iters:
            await iterator.close()


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
            value = await self._source.next()
            if value is None:
                self._done = True
                return self._acc
            self._acc = self._fn(self._acc, value)

    async def close(self) -> None:
        await self._source.close()

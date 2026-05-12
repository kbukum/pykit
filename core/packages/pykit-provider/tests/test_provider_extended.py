"""Extended tests for pykit_provider — error handling, edge cases, async patterns,
type system, security, and composition."""

from __future__ import annotations

import asyncio

import pytest

from pykit_provider import (
    BoxIterator,
    Duplex,
    DuplexStream,
    Provider,
    RequestResponse,
    RequestResponseFunc,
    Sink,
    Stream,
)

# ---------------------------------------------------------------------------
# Concrete helpers
# ---------------------------------------------------------------------------


class ErrorBoxIterator(BoxIterator[int]):
    """BoxIterator that raises after yielding a given number of items."""

    def __init__(self, items: list[int], error_at: int, error: Exception) -> None:
        self._items = items
        self._index = 0
        self._error_at = error_at
        self._error = error

    async def next(self) -> int | None:
        if self._index == self._error_at:
            raise self._error
        if self._index >= len(self._items):
            return None
        val = self._items[self._index]
        self._index += 1
        return val


class SingleItemIterator(BoxIterator[str]):
    """BoxIterator with exactly one item."""

    def __init__(self, item: str) -> None:
        self._item: str | None = item

    async def next(self) -> str | None:
        val = self._item
        self._item = None
        return val


class CountingIterator(BoxIterator[int]):
    """BoxIterator that yields 0..limit-1."""

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._current = 0

    async def next(self) -> int | None:
        if self._current >= self._limit:
            return None
        val = self._current
        self._current += 1
        return val


class CloseTrackingIterator(BoxIterator[str]):
    """BoxIterator that tracks close() calls."""

    def __init__(self, items: list[str]) -> None:
        self._items = list(items)
        self._index = 0
        self.close_count = 0
        self._closed = False

    async def next(self) -> str | None:
        if self._closed:
            return None
        if self._index >= len(self._items):
            return None
        val = self._items[self._index]
        self._index += 1
        return val

    async def close(self) -> None:
        self.close_count += 1
        self._closed = True


class ErrorDuplexStream(DuplexStream[str, str]):
    """DuplexStream that raises on send/recv after a threshold."""

    def __init__(self, send_error_at: int = -1, recv_error_at: int = -1) -> None:
        self._send_count = 0
        self._recv_count = 0
        self._send_error_at = send_error_at
        self._recv_error_at = recv_error_at

    async def send(self, input: str) -> None:
        if self._send_count == self._send_error_at:
            raise ConnectionError("send failed")
        self._send_count += 1

    async def recv(self) -> str | None:
        if self._recv_count == self._recv_error_at:
            raise ConnectionError("recv failed")
        self._recv_count += 1
        return f"msg-{self._recv_count}"

    async def close(self) -> None:
        pass


class StatefulDuplexStream(DuplexStream[str, str]):
    """DuplexStream that tracks closed state and raises on post-close ops."""

    def __init__(self) -> None:
        self._closed = False
        self.close_count = 0
        self._recv_q: asyncio.Queue[str | None] = asyncio.Queue()
        self._send_log: list[str] = []

    async def send(self, input: str) -> None:
        if self._closed:
            raise RuntimeError("stream is closed")
        self._send_log.append(input)

    async def recv(self) -> str | None:
        if self._closed:
            return None
        return await self._recv_q.get()

    async def close(self) -> None:
        self.close_count += 1
        self._closed = True


class AsyncSlowIterator(BoxIterator[int]):
    """BoxIterator with an artificial async delay per item."""

    def __init__(self, items: list[int], delay: float = 0.01) -> None:
        self._items = items
        self._index = 0
        self._delay = delay

    async def next(self) -> int | None:
        if self._index >= len(self._items):
            return None
        await asyncio.sleep(self._delay)
        val = self._items[self._index]
        self._index += 1
        return val


class ErrorProvider:
    """Provider whose is_available raises."""

    @property
    def name(self) -> str:
        return "error-provider"

    async def is_available(self) -> bool:
        raise ConnectionError("cannot reach backend")


class ComplexTypeIterator(BoxIterator[dict[str, list[int]]]):
    """BoxIterator yielding complex nested types."""

    def __init__(self, items: list[dict[str, list[int]]]) -> None:
        self._items = items
        self._index = 0

    async def next(self) -> dict[str, list[int]] | None:
        if self._index >= len(self._items):
            return None
        val = self._items[self._index]
        self._index += 1
        return val


class TupleIterator(BoxIterator[tuple[int, str]]):
    """BoxIterator yielding tuples."""

    def __init__(self, items: list[tuple[int, str]]) -> None:
        self._items = items
        self._index = 0

    async def next(self) -> tuple[int, str] | None:
        if self._index >= len(self._items):
            return None
        val = self._items[self._index]
        self._index += 1
        return val


# ---------------------------------------------------------------------------
# 1. Error Handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.mark.parametrize(
        "error",
        [
            ValueError("bad value"),
            TypeError("wrong type"),
            RuntimeError("runtime failure"),
        ],
        ids=["ValueError", "TypeError", "RuntimeError"],
    )
    async def test_request_response_func_propagates_errors(self, error: Exception) -> None:
        async def failing(_: str) -> str:
            raise error

        func = RequestResponseFunc("fail", failing)
        with pytest.raises(type(error), match=str(error)):
            await func.execute("anything")

    async def test_box_iterator_next_raises_mid_iteration(self) -> None:
        it = ErrorBoxIterator([1, 2, 3], error_at=2, error=RuntimeError("boom"))
        assert await it.next() == 1
        assert await it.next() == 2
        with pytest.raises(RuntimeError, match="boom"):
            await it.next()

    async def test_box_iterator_anext_propagates_exception(self) -> None:
        it = ErrorBoxIterator([10], error_at=1, error=ValueError("bad"))
        assert await it.__anext__() == 10
        with pytest.raises(ValueError, match="bad"):
            await it.__anext__()

    async def test_box_iterator_async_for_propagates_error(self) -> None:
        it = ErrorBoxIterator([1, 2], error_at=2, error=OSError("disk"))
        collected: list[int] = []
        with pytest.raises(OSError, match="disk"):
            async for val in it:
                collected.append(val)
        assert collected == [1, 2]

    async def test_duplex_stream_send_raises(self) -> None:
        stream = ErrorDuplexStream(send_error_at=0)
        with pytest.raises(ConnectionError, match="send failed"):
            await stream.send("hello")

    async def test_duplex_stream_recv_raises(self) -> None:
        stream = ErrorDuplexStream(recv_error_at=0)
        with pytest.raises(ConnectionError, match="recv failed"):
            await stream.recv()

    async def test_provider_is_available_raises(self) -> None:
        p = ErrorProvider()
        assert isinstance(p, Provider)
        with pytest.raises(ConnectionError, match="cannot reach backend"):
            await p.is_available()


# ---------------------------------------------------------------------------
# 2. Edge Cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    async def test_box_iterator_single_item(self) -> None:
        it = SingleItemIterator("only")
        collected: list[str] = []
        async for val in it:
            collected.append(val)
        assert collected == ["only"]

    async def test_box_iterator_large_iteration(self) -> None:
        limit = 2000
        it = CountingIterator(limit)
        collected: list[int] = []
        async for val in it:
            collected.append(val)
        assert len(collected) == limit
        assert collected[0] == 0
        assert collected[-1] == limit - 1

    async def test_box_iterator_close_idempotent(self) -> None:
        it = CloseTrackingIterator(["a", "b"])
        await it.close()
        await it.close()
        await it.close()
        assert it.close_count == 3

    async def test_box_iterator_iteration_after_close(self) -> None:
        it = CloseTrackingIterator(["a", "b"])
        assert await it.next() == "a"
        await it.close()
        assert await it.next() is None

    async def test_duplex_stream_close_idempotent(self) -> None:
        stream = StatefulDuplexStream()
        await stream.close()
        await stream.close()
        assert stream.close_count == 2

    async def test_duplex_stream_recv_after_close(self) -> None:
        stream = StatefulDuplexStream()
        await stream.close()
        result = await stream.recv()
        assert result is None

    async def test_duplex_stream_send_after_close(self) -> None:
        stream = StatefulDuplexStream()
        await stream.close()
        with pytest.raises(RuntimeError, match="stream is closed"):
            await stream.send("late message")

    async def test_request_response_func_none_name(self) -> None:
        func = RequestResponseFunc(None, self._identity)  # type: ignore[arg-type]
        assert func.name is None

    async def test_request_response_func_empty_name(self) -> None:
        func = RequestResponseFunc("", self._identity)
        assert func.name == ""
        assert await func.execute("x") == "x"

    async def test_request_response_func_unicode_name(self) -> None:
        func = RequestResponseFunc("提供者-🚀", self._identity)
        assert func.name == "提供者-🚀"

    async def test_provider_is_available_false_still_satisfies_protocol(self) -> None:
        class FalseProvider:
            @property
            def name(self) -> str:
                return "down"

            async def is_available(self) -> bool:
                return False

        p = FalseProvider()
        assert isinstance(p, Provider)
        assert await p.is_available() is False

    @staticmethod
    async def _identity(x: str) -> str:
        return x


# ---------------------------------------------------------------------------
# 3. Async Patterns
# ---------------------------------------------------------------------------


class TestAsyncPatterns:
    async def test_concurrent_box_iterator_consumption(self) -> None:
        """Two coroutines consuming the same iterator see disjoint items."""
        it = CountingIterator(10)
        results_a: list[int] = []
        results_b: list[int] = []

        async def consume_a() -> None:
            for _ in range(5):
                val = await it.next()
                if val is not None:
                    results_a.append(val)

        async def consume_b() -> None:
            for _ in range(5):
                val = await it.next()
                if val is not None:
                    results_b.append(val)

        await asyncio.gather(consume_a(), consume_b())
        combined = sorted(results_a + results_b)
        assert combined == list(range(10))

    async def test_concurrent_duplex_stream_send_recv(self) -> None:
        stream = StatefulDuplexStream()
        sent: list[str] = []
        received: list[str | None] = []

        async def sender() -> None:
            for i in range(3):
                msg = f"s{i}"
                await stream.send(msg)
                sent.append(msg)

        async def push_messages() -> None:
            for i in range(3):
                await stream._recv_q.put(f"r{i}")
            await stream._recv_q.put(None)

        async def receiver() -> None:
            while True:
                val = await stream.recv()
                received.append(val)
                if val is None:
                    break

        await asyncio.gather(sender(), push_messages(), receiver())
        assert sent == ["s0", "s1", "s2"]
        assert received == ["r0", "r1", "r2", None]

    async def test_request_response_func_slow_async(self) -> None:
        async def slow(x: int) -> int:
            await asyncio.sleep(0.05)
            return x * 10

        func = RequestResponseFunc("slow", slow)
        result = await func.execute(3)
        assert result == 30

    async def test_box_iterator_with_async_sleep(self) -> None:
        it = AsyncSlowIterator([10, 20, 30], delay=0.01)
        collected: list[int] = []
        async for val in it:
            collected.append(val)
        assert collected == [10, 20, 30]

    async def test_cancellation_during_box_iterator(self) -> None:
        it = AsyncSlowIterator(list(range(100)), delay=0.05)
        collected: list[int] = []

        async def consume() -> None:
            async for val in it:
                collected.append(val)

        task = asyncio.create_task(consume())
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # Should have collected some items but not all
        assert 0 < len(collected) < 100

    async def test_cancellation_during_duplex_recv(self) -> None:
        stream = StatefulDuplexStream()

        async def blocking_recv() -> str | None:
            return await stream.recv()

        task = asyncio.create_task(blocking_recv())
        await asyncio.sleep(0.02)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


# ---------------------------------------------------------------------------
# 4. Type System / Protocol verification
# ---------------------------------------------------------------------------


class TestTypeSystem:
    async def test_partial_implementation_not_provider(self) -> None:
        """A class missing is_available does not satisfy Provider."""

        class NameOnly:
            @property
            def name(self) -> str:
                return "incomplete"

        assert not isinstance(NameOnly(), Provider)

    async def test_missing_name_not_provider(self) -> None:
        class AvailableOnly:
            async def is_available(self) -> bool:
                return True

        assert not isinstance(AvailableOnly(), Provider)

    async def test_wrong_signature_isinstance_behavior(self) -> None:
        """runtime_checkable only checks method existence, not signatures."""

        class WrongSig:
            @property
            def name(self) -> str:
                return "wrong"

            async def is_available(self) -> str:  # wrong return type
                return "yes"

        # runtime_checkable doesn't validate signatures — just attribute presence
        assert isinstance(WrongSig(), Provider)

    async def test_request_response_isinstance_only_checks_structure(self) -> None:
        """RequestResponse[str, int] vs [int, str] — both pass isinstance."""

        class StrToInt:
            @property
            def name(self) -> str:
                return "s2i"

            async def is_available(self) -> bool:
                return True

            async def execute(self, input: str) -> int:
                return len(input)

        class IntToStr:
            @property
            def name(self) -> str:
                return "i2s"

            async def is_available(self) -> bool:
                return True

            async def execute(self, input: int) -> str:
                return str(input)

        assert isinstance(StrToInt(), RequestResponse)
        assert isinstance(IntToStr(), RequestResponse)

    async def test_box_iterator_complex_dict_type(self) -> None:
        items = [{"a": [1, 2]}, {"b": [3, 4, 5]}]
        it = ComplexTypeIterator(items)
        collected: list[dict[str, list[int]]] = []
        async for val in it:
            collected.append(val)
        assert collected == items

    async def test_box_iterator_tuple_type(self) -> None:
        items = [(1, "a"), (2, "b")]
        it = TupleIterator(items)
        collected: list[tuple[int, str]] = []
        async for val in it:
            collected.append(val)
        assert collected == items

    async def test_box_iterator_list_type(self) -> None:
        class ListIterator(BoxIterator[list[int]]):
            def __init__(self, items: list[list[int]]) -> None:
                self._items = items
                self._idx = 0

            async def next(self) -> list[int] | None:
                if self._idx >= len(self._items):
                    return None
                val = self._items[self._idx]
                self._idx += 1
                return val

        it = ListIterator([[1, 2], [3, 4, 5], []])
        collected: list[list[int]] = []
        async for val in it:
            collected.append(val)
        assert collected == [[1, 2], [3, 4, 5], []]

    async def test_plain_object_not_request_response(self) -> None:
        assert not isinstance(object(), RequestResponse)

    async def test_plain_object_not_stream_provider(self) -> None:
        assert not isinstance(object(), Stream)

    async def test_plain_object_not_sink(self) -> None:
        assert not isinstance(object(), Sink)

    async def test_plain_object_not_duplex(self) -> None:
        assert not isinstance(object(), Duplex)


# ---------------------------------------------------------------------------
# 5. Security / Robustness
# ---------------------------------------------------------------------------


class TestSecurity:
    @pytest.mark.parametrize(
        "name",
        [
            "<script>alert('xss')</script>",
            "'; DROP TABLE providers; --",
            "provider\x00name",
            "../../../etc/passwd",
            "a" * 10_000,
        ],
        ids=["xss", "sql-injection", "null-byte", "path-traversal", "very-long-name"],
    )
    async def test_injection_in_provider_names(self, name: str) -> None:
        """Names are stored as-is — no sanitization, no crash."""

        async def noop(_: str) -> str:
            return "ok"

        func = RequestResponseFunc(name, noop)
        assert func.name == name
        assert await func.execute("test") == "ok"

    async def test_large_input_to_execute(self) -> None:
        large = "x" * 1_000_000

        async def echo(s: str) -> str:
            return s

        func = RequestResponseFunc("big", echo)
        result = await func.execute(large)
        assert len(result) == 1_000_000

    async def test_large_input_to_sink(self) -> None:
        class MemSink:
            def __init__(self) -> None:
                self.data: list[bytes] = []

            @property
            def name(self) -> str:
                return "mem-sink"

            async def is_available(self) -> bool:
                return True

            async def send(self, input: bytes) -> None:
                self.data.append(input)

        sink = MemSink()
        big = b"\x00" * 500_000
        await sink.send(big)
        assert len(sink.data[0]) == 500_000

    async def test_null_bytes_in_inputs(self) -> None:
        async def echo(s: str) -> str:
            return s

        func = RequestResponseFunc("nb", echo)
        result = await func.execute("hello\x00world")
        assert result == "hello\x00world"


# ---------------------------------------------------------------------------
# 6. Composition
# ---------------------------------------------------------------------------


class TestComposition:
    async def test_chained_request_response_funcs(self) -> None:
        """Output of one RequestResponseFunc feeds into another."""

        async def double(x: int) -> int:
            return x * 2

        async def add_ten(x: int) -> int:
            return x + 10

        step1 = RequestResponseFunc("double", double)
        step2 = RequestResponseFunc("add10", add_ten)

        intermediate = await step1.execute(5)
        result = await step2.execute(intermediate)
        assert result == 20

    async def test_triple_chain(self) -> None:
        async def to_str(x: int) -> str:
            return str(x)

        async def upper(s: str) -> str:
            return s.upper()

        async def wrap(s: str) -> str:
            return f"[{s}]"

        chain: list[RequestResponseFunc] = [
            RequestResponseFunc("to_str", to_str),
            RequestResponseFunc("upper", upper),
            RequestResponseFunc("wrap", wrap),
        ]
        val: object = 42
        for step in chain:
            val = await step.execute(val)
        assert val == "[42]"

    async def test_stream_provider_collect_all(self) -> None:
        """Collect all results from a Stream into a list."""

        class NumberStream:
            @property
            def name(self) -> str:
                return "nums"

            async def is_available(self) -> bool:
                return True

            async def execute(self, input: int) -> BoxIterator[int]:
                return CountingIterator(input)

        sp = NumberStream()
        it = await sp.execute(5)
        results: list[int] = []
        async for val in it:
            results.append(val)
        assert results == [0, 1, 2, 3, 4]

    async def test_sink_collecting_from_stream_output(self) -> None:
        """Pipe Stream output into a Sink."""

        class WordStream:
            @property
            def name(self) -> str:
                return "words"

            async def is_available(self) -> bool:
                return True

            async def execute(self, input: str) -> BoxIterator[str]:
                class WI(BoxIterator[str]):
                    def __init__(self, words: list[str]) -> None:
                        self._words = words
                        self._idx = 0

                    async def next(self) -> str | None:
                        if self._idx >= len(self._words):
                            return None
                        val = self._words[self._idx]
                        self._idx += 1
                        return val

                return WI(input.split())

        class CollectSink:
            def __init__(self) -> None:
                self.items: list[str] = []

            @property
            def name(self) -> str:
                return "collector"

            async def is_available(self) -> bool:
                return True

            async def send(self, input: str) -> None:
                self.items.append(input)

        stream = WordStream()
        sink = CollectSink()

        it = await stream.execute("hello world foo")
        async for word in it:
            await sink.send(word)

        assert sink.items == ["hello", "world", "foo"]

    async def test_request_response_func_with_complex_io(self) -> None:
        """RequestResponseFunc with dict input and list output."""

        async def extract_keys(d: dict[str, int]) -> list[str]:
            return sorted(d.keys())

        func = RequestResponseFunc("keys", extract_keys)
        result = await func.execute({"b": 2, "a": 1, "c": 3})
        assert result == ["a", "b", "c"]

    async def test_duplex_echo_pattern(self) -> None:
        """Use a DuplexStream in an echo pattern."""

        class EchoDuplexStream(DuplexStream[str, str]):
            def __init__(self) -> None:
                self._q: asyncio.Queue[str | None] = asyncio.Queue()
                self._closed = False

            async def send(self, input: str) -> None:
                if self._closed:
                    raise RuntimeError("closed")
                await self._q.put(input.upper())

            async def recv(self) -> str | None:
                if self._closed and self._q.empty():
                    return None
                return await self._q.get()

            async def close(self) -> None:
                self._closed = True
                await self._q.put(None)

        stream = EchoDuplexStream()
        await stream.send("hello")
        await stream.send("world")
        assert await stream.recv() == "HELLO"
        assert await stream.recv() == "WORLD"
        await stream.close()
        assert await stream.recv() is None

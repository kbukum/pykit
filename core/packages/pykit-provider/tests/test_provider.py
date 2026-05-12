"""Comprehensive tests for pykit_provider protocols and helpers."""

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
# Concrete helpers used across tests
# ---------------------------------------------------------------------------


class SimpleProvider:
    """Minimal Provider implementation."""

    @property
    def name(self) -> str:
        return "simple"

    async def is_available(self) -> bool:
        return True


class UnavailableProvider:
    """Provider that reports itself as unavailable."""

    @property
    def name(self) -> str:
        return "unavailable"

    async def is_available(self) -> bool:
        return False


class ListBoxIterator(BoxIterator[str]):
    """BoxIterator backed by a list of strings."""

    def __init__(self, items: list[str]) -> None:
        self._items = list(items)
        self._index = 0
        self.closed = False

    async def next(self) -> str | None:
        if self._index >= len(self._items):
            return None
        val = self._items[self._index]
        self._index += 1
        return val

    async def close(self) -> None:
        self.closed = True


class EmptyBoxIterator(BoxIterator[int]):
    """BoxIterator that is immediately exhausted."""

    async def next(self) -> int | None:
        return None


class EchoRequestResponse:
    """RequestResponse that echoes its input uppercased."""

    @property
    def name(self) -> str:
        return "echo-rr"

    async def is_available(self) -> bool:
        return True

    async def execute(self, input: str) -> str:
        return input.upper()


class WordStream:
    """Stream that splits input into a stream of words."""

    @property
    def name(self) -> str:
        return "word-stream"

    async def is_available(self) -> bool:
        return True

    async def execute(self, input: str) -> BoxIterator[str]:
        return ListBoxIterator(input.split())


class LogSink:
    """Sink that collects sent messages."""

    def __init__(self) -> None:
        self.messages: list[str] = []

    @property
    def name(self) -> str:
        return "log-sink"

    async def is_available(self) -> bool:
        return True

    async def send(self, input: str) -> None:
        self.messages.append(input)


class InMemoryDuplexStream(DuplexStream[str, str]):
    """DuplexStream backed by two asyncio queues."""

    def __init__(self) -> None:
        self._send_q: asyncio.Queue[str] = asyncio.Queue()
        self._recv_q: asyncio.Queue[str | None] = asyncio.Queue()
        self._closed = False

    async def send(self, input: str) -> None:
        await self._send_q.put(input)

    async def recv(self) -> str | None:
        return await self._recv_q.get()

    async def close(self) -> None:
        self._closed = True
        await self._recv_q.put(None)

    # helpers for tests
    async def push_recv(self, val: str) -> None:
        await self._recv_q.put(val)

    async def pop_sent(self) -> str:
        return await self._send_q.get()


class ChatDuplex:
    """Duplex provider returning an InMemoryDuplexStream."""

    def __init__(self) -> None:
        self.last_stream: InMemoryDuplexStream | None = None

    @property
    def name(self) -> str:
        return "chat-duplex"

    async def is_available(self) -> bool:
        return True

    async def open(self) -> InMemoryDuplexStream:
        self.last_stream = InMemoryDuplexStream()
        return self.last_stream


# ---------------------------------------------------------------------------
# 1. Provider protocol
# ---------------------------------------------------------------------------


class TestProviderProtocol:
    async def test_isinstance_check(self) -> None:
        assert isinstance(SimpleProvider(), Provider)

    async def test_unavailable_provider(self) -> None:
        p = UnavailableProvider()
        assert isinstance(p, Provider)
        assert p.name == "unavailable"
        assert await p.is_available() is False

    async def test_name_and_availability(self) -> None:
        p = SimpleProvider()
        assert p.name == "simple"
        assert await p.is_available() is True

    async def test_non_provider_not_recognised(self) -> None:
        assert not isinstance("a string", Provider)
        assert not isinstance(42, Provider)


# ---------------------------------------------------------------------------
# 2. BoxIterator
# ---------------------------------------------------------------------------


class TestBoxIterator:
    async def test_next_returns_items(self) -> None:
        it = ListBoxIterator(["a", "b", "c"])
        assert await it.next() == "a"
        assert await it.next() == "b"
        assert await it.next() == "c"
        assert await it.next() is None

    async def test_close(self) -> None:
        it = ListBoxIterator(["x"])
        assert it.closed is False
        await it.close()
        assert it.closed is True

    async def test_aiter_returns_self(self) -> None:
        it = ListBoxIterator(["x"])
        assert it.__aiter__() is it

    async def test_anext_yields_items(self) -> None:
        it = ListBoxIterator(["a", "b"])
        assert await it.__anext__() == "a"
        assert await it.__anext__() == "b"

    async def test_anext_raises_stop_when_exhausted(self) -> None:
        it = EmptyBoxIterator()
        with pytest.raises(StopAsyncIteration):
            await it.__anext__()

    async def test_async_for_loop(self) -> None:
        it = ListBoxIterator(["x", "y", "z"])
        collected: list[str] = []
        async for val in it:
            collected.append(val)
        assert collected == ["x", "y", "z"]

    async def test_async_for_empty(self) -> None:
        it = EmptyBoxIterator()
        collected: list[int] = []
        async for val in it:
            collected.append(val)
        assert collected == []

    async def test_default_close_is_noop(self) -> None:
        """The base close() does nothing but should not raise."""
        it = EmptyBoxIterator()
        await it.close()  # should not raise


# ---------------------------------------------------------------------------
# 3. RequestResponse protocol
# ---------------------------------------------------------------------------


class TestRequestResponse:
    async def test_isinstance_check(self) -> None:
        assert isinstance(EchoRequestResponse(), RequestResponse)

    async def test_execute(self) -> None:
        rr = EchoRequestResponse()
        assert await rr.execute("hello") == "HELLO"

    async def test_name_and_available(self) -> None:
        rr = EchoRequestResponse()
        assert rr.name == "echo-rr"
        assert await rr.is_available() is True

    async def test_also_satisfies_provider(self) -> None:
        assert isinstance(EchoRequestResponse(), Provider)


# ---------------------------------------------------------------------------
# 4. Stream protocol
# ---------------------------------------------------------------------------


class TestStream:
    async def test_isinstance_check(self) -> None:
        assert isinstance(WordStream(), Stream)

    async def test_execute_returns_box_iterator(self) -> None:
        sp = WordStream()
        it = await sp.execute("one two three")
        assert isinstance(it, BoxIterator)

    async def test_stream_items(self) -> None:
        sp = WordStream()
        it = await sp.execute("one two three")
        collected: list[str] = []
        async for word in it:
            collected.append(word)
        assert collected == ["one", "two", "three"]

    async def test_empty_stream(self) -> None:
        sp = WordStream()
        it = await sp.execute("")
        # "".split() returns [] so the iterator is immediately exhausted
        collected: list[str] = []
        async for word in it:
            collected.append(word)
        assert collected == []

    async def test_also_satisfies_provider(self) -> None:
        assert isinstance(WordStream(), Provider)


# ---------------------------------------------------------------------------
# 5. Sink protocol
# ---------------------------------------------------------------------------


class TestSink:
    async def test_isinstance_check(self) -> None:
        assert isinstance(LogSink(), Sink)

    async def test_send_collects(self) -> None:
        sink = LogSink()
        await sink.send("msg1")
        await sink.send("msg2")
        assert sink.messages == ["msg1", "msg2"]

    async def test_name_and_available(self) -> None:
        sink = LogSink()
        assert sink.name == "log-sink"
        assert await sink.is_available() is True

    async def test_also_satisfies_provider(self) -> None:
        assert isinstance(LogSink(), Provider)


# ---------------------------------------------------------------------------
# 6. DuplexStream
# ---------------------------------------------------------------------------


class TestDuplexStream:
    async def test_send_and_recv(self) -> None:
        stream = InMemoryDuplexStream()
        await stream.push_recv("pong")
        assert await stream.recv() == "pong"

        await stream.send("ping")
        assert await stream.pop_sent() == "ping"

    async def test_close_signals_none(self) -> None:
        stream = InMemoryDuplexStream()
        await stream.close()
        assert await stream.recv() is None

    async def test_multiple_send_recv(self) -> None:
        stream = InMemoryDuplexStream()
        for i in range(5):
            await stream.send(f"m{i}")
        for i in range(5):
            assert await stream.pop_sent() == f"m{i}"

    async def test_recv_after_push(self) -> None:
        stream = InMemoryDuplexStream()
        await stream.push_recv("a")
        await stream.push_recv("b")
        assert await stream.recv() == "a"
        assert await stream.recv() == "b"


# ---------------------------------------------------------------------------
# 7. Duplex protocol
# ---------------------------------------------------------------------------


class TestDuplex:
    async def test_isinstance_check(self) -> None:
        assert isinstance(ChatDuplex(), Duplex)

    async def test_open_returns_duplex_stream(self) -> None:
        d = ChatDuplex()
        stream = await d.open()
        assert isinstance(stream, DuplexStream)

    async def test_round_trip(self) -> None:
        d = ChatDuplex()
        stream = await d.open()
        assert isinstance(stream, InMemoryDuplexStream)

        await stream.send("hello")
        assert await stream.pop_sent() == "hello"

        await stream.push_recv("world")
        assert await stream.recv() == "world"

    async def test_close_stream(self) -> None:
        d = ChatDuplex()
        stream = await d.open()
        await stream.close()
        assert await stream.recv() is None

    async def test_name_and_available(self) -> None:
        d = ChatDuplex()
        assert d.name == "chat-duplex"
        assert await d.is_available() is True

    async def test_also_satisfies_provider(self) -> None:
        assert isinstance(ChatDuplex(), Provider)


# ---------------------------------------------------------------------------
# 8. RequestResponseFunc
# ---------------------------------------------------------------------------


class TestRequestResponseFunc:
    async def test_name_property(self) -> None:
        func = RequestResponseFunc("test-fn", self._double)
        assert func.name == "test-fn"

    async def test_is_available_returns_true(self) -> None:
        func = RequestResponseFunc("test-fn", self._double)
        assert await func.is_available() is True

    async def test_execute_delegates_to_callable(self) -> None:
        func = RequestResponseFunc("doubler", self._double)
        assert await func.execute(5) == 10

    async def test_execute_with_lambda(self) -> None:
        func = RequestResponseFunc("upper", self._upper)
        assert await func.execute("abc") == "ABC"

    async def test_satisfies_request_response_protocol(self) -> None:
        func = RequestResponseFunc("rr", self._double)
        assert isinstance(func, RequestResponse)

    async def test_satisfies_provider_protocol(self) -> None:
        func = RequestResponseFunc("p", self._double)
        assert isinstance(func, Provider)

    async def test_different_callables(self) -> None:
        """Ensure different callables produce different results."""
        adder = RequestResponseFunc("add1", self._add_one)
        doubler = RequestResponseFunc("dbl", self._double)
        assert await adder.execute(3) == 4
        assert await doubler.execute(3) == 6

    async def test_execute_with_none_input(self) -> None:
        async def greet(_: None) -> str:
            return "hi"

        func = RequestResponseFunc("greeter", greet)
        assert await func.execute(None) == "hi"

    # --- async helper callables ---

    @staticmethod
    async def _double(x: int) -> int:
        return x * 2

    @staticmethod
    async def _upper(s: str) -> str:
        return s.upper()

    @staticmethod
    async def _add_one(x: int) -> int:
        return x + 1

"""Middleware chaining tests for provider shapes."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from pykit_provider import (
    BoxIterator,
    Duplex,
    DuplexStream,
    RequestResponse,
    Sink,
    StreamProvider,
    chain,
    chain_duplex,
    chain_sink,
    chain_stream,
)


@dataclass
class RecordingIterator(BoxIterator[str]):
    items: list[str]
    index: int = 0

    async def next(self) -> str | None:
        if self.index >= len(self.items):
            return None
        value = self.items[self.index]
        self.index += 1
        return value


class EchoRequestResponse:
    @property
    def name(self) -> str:
        return "echo"

    async def is_available(self) -> bool:
        return True

    async def execute(self, input: str) -> str:
        return input


class RecordingSink:
    def __init__(self) -> None:
        self.messages: list[str] = []

    @property
    def name(self) -> str:
        return "sink"

    async def is_available(self) -> bool:
        return True

    async def send(self, input: str) -> None:
        self.messages.append(input)


class WordStream:
    @property
    def name(self) -> str:
        return "stream"

    async def is_available(self) -> bool:
        return True

    async def execute(self, input: str) -> RecordingIterator:
        return RecordingIterator(input.split())


class MemoryDuplexStream(DuplexStream[str, str]):
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send(self, input: str) -> None:
        self.sent.append(input)

    async def recv(self) -> str | None:
        return None

    async def close(self) -> None:
        return None


class MemoryDuplex:
    def __init__(self) -> None:
        self.stream = MemoryDuplexStream()

    @property
    def name(self) -> str:
        return "duplex"

    async def is_available(self) -> bool:
        return True

    async def open(self) -> MemoryDuplexStream:
        return self.stream


def wrap_request_response(label: str, order: list[str]):
    def middleware(inner: RequestResponse[str, str]) -> RequestResponse[str, str]:
        class Wrapped:
            @property
            def name(self) -> str:
                return inner.name

            async def is_available(self) -> bool:
                return await inner.is_available()

            async def execute(self, input: str) -> str:
                order.append(label)
                return await inner.execute(input)

        return Wrapped()

    return middleware


def wrap_sink(label: str, order: list[str]):
    def middleware(inner: Sink[str]) -> Sink[str]:
        class Wrapped:
            @property
            def name(self) -> str:
                return inner.name

            async def is_available(self) -> bool:
                return await inner.is_available()

            async def send(self, input: str) -> None:
                order.append(label)
                await inner.send(input)

        return Wrapped()

    return middleware


def wrap_stream(label: str, order: list[str]):
    def middleware(inner: StreamProvider[str, str]) -> StreamProvider[str, str]:
        class Wrapped:
            @property
            def name(self) -> str:
                return inner.name

            async def is_available(self) -> bool:
                return await inner.is_available()

            async def execute(self, input: str) -> RecordingIterator:
                order.append(label)
                return await inner.execute(input)

        return Wrapped()

    return middleware


def wrap_duplex(label: str, order: list[str]):
    def middleware(inner: Duplex[str, str]) -> Duplex[str, str]:
        class Wrapped:
            @property
            def name(self) -> str:
                return inner.name

            async def is_available(self) -> bool:
                return await inner.is_available()

            async def open(self) -> DuplexStream[str, str]:
                order.append(label)
                return await inner.open()

        return Wrapped()

    return middleware


class TestMiddlewareChains:
    @pytest.mark.asyncio
    async def test_request_response_chain_left_to_right(self) -> None:
        order: list[str] = []
        provider = chain(
            wrap_request_response("first", order),
            wrap_request_response("second", order),
        )(EchoRequestResponse())

        assert await provider.execute("hello") == "hello"
        assert order == ["first", "second"]

    @pytest.mark.asyncio
    async def test_sink_chain_left_to_right(self) -> None:
        order: list[str] = []
        sink = RecordingSink()
        wrapped = chain_sink(wrap_sink("first", order), wrap_sink("second", order))(sink)

        await wrapped.send("payload")

        assert order == ["first", "second"]
        assert sink.messages == ["payload"]

    @pytest.mark.asyncio
    async def test_stream_chain_left_to_right(self) -> None:
        order: list[str] = []
        provider = chain_stream(wrap_stream("first", order), wrap_stream("second", order))(WordStream())

        iterator = await provider.execute("one two")
        assert [item async for item in iterator] == ["one", "two"]
        assert order == ["first", "second"]

    @pytest.mark.asyncio
    async def test_duplex_chain_left_to_right(self) -> None:
        order: list[str] = []
        duplex = MemoryDuplex()
        wrapped = chain_duplex(wrap_duplex("first", order), wrap_duplex("second", order))(duplex)

        stream = await wrapped.open()
        await stream.send("hello")

        assert order == ["first", "second"]
        assert duplex.stream.sent == ["hello"]

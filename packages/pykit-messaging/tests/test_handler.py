"""Tests for handler chain types and middleware composition."""

from __future__ import annotations

from pykit_messaging.handler import FuncHandler, MessageHandlerProtocol, chain_handlers
from pykit_messaging.types import Message


def _make_msg(value: bytes = b"test") -> Message:
    return Message(key=None, value=value, topic="t", partition=0, offset=0)


class TestFuncHandler:
    async def test_func_handler_delegates_to_callable(self) -> None:
        received: list[Message] = []

        async def fn(msg: Message) -> None:
            received.append(msg)

        handler = FuncHandler(fn)
        msg = _make_msg()
        await handler.handle(msg)

        assert len(received) == 1
        assert received[0] is msg

    async def test_func_handler_satisfies_protocol(self) -> None:
        async def fn(msg: Message) -> None:
            pass

        handler = FuncHandler(fn)
        assert isinstance(handler, MessageHandlerProtocol)


class TestChainHandlers:
    async def test_chain_no_middleware(self) -> None:
        calls: list[str] = []

        async def fn(msg: Message) -> None:
            calls.append("base")

        base = FuncHandler(fn)
        chained = chain_handlers(base)
        await chained.handle(_make_msg())

        assert calls == ["base"]

    async def test_chain_single_middleware(self) -> None:
        calls: list[str] = []

        async def fn(msg: Message) -> None:
            calls.append("base")

        def logging_mw(inner: MessageHandlerProtocol) -> MessageHandlerProtocol:
            class Wrapper:
                async def handle(self, msg: Message) -> None:
                    calls.append("before")
                    await inner.handle(msg)
                    calls.append("after")

            return Wrapper()

        base = FuncHandler(fn)
        chained = chain_handlers(base, logging_mw)
        await chained.handle(_make_msg())

        assert calls == ["before", "base", "after"]

    async def test_chain_multiple_middlewares(self) -> None:
        calls: list[str] = []

        async def fn(msg: Message) -> None:
            calls.append("base")

        def mw_a(inner: MessageHandlerProtocol) -> MessageHandlerProtocol:
            class Wrapper:
                async def handle(self, msg: Message) -> None:
                    calls.append("a-before")
                    await inner.handle(msg)
                    calls.append("a-after")

            return Wrapper()

        def mw_b(inner: MessageHandlerProtocol) -> MessageHandlerProtocol:
            class Wrapper:
                async def handle(self, msg: Message) -> None:
                    calls.append("b-before")
                    await inner.handle(msg)
                    calls.append("b-after")

            return Wrapper()

        base = FuncHandler(fn)
        # mw_b is outermost: b runs first, then a, then base
        chained = chain_handlers(base, mw_a, mw_b)
        await chained.handle(_make_msg())

        assert calls == ["b-before", "a-before", "base", "a-after", "b-after"]

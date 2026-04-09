"""Tests for pykit-hook module — uses test-local event types only."""

from __future__ import annotations

from dataclasses import dataclass

from pykit_hook.registry import Registry
from pykit_hook.types import (
    Action,
    Event,
    Result,
    abort,
    continue_,
    modify,
)

# ---------------------------------------------------------------------------
# Test-local event types (no domain imports)
# ---------------------------------------------------------------------------

PING = "ping"
PONG = "pong"


@dataclass
class PingEvent:
    """Simple test event."""

    value: str = ""
    type: str = PING


@dataclass
class PongEvent:
    """Another simple test event."""

    count: int = 0
    type: str = PONG


class TestEventProtocol:
    """Test-local events satisfy the Event protocol."""

    def test_ping_is_event(self) -> None:
        e: Event = PingEvent(value="hello")
        assert e.type == PING

    def test_pong_is_event(self) -> None:
        e: Event = PongEvent(count=42)
        assert e.type == PONG


class TestAction:
    """Action enum values."""

    def test_values(self) -> None:
        assert Action.CONTINUE.value == "continue"
        assert Action.ABORT.value == "abort"
        assert Action.MODIFY.value == "modify"


class TestResult:
    """Result defaults and construction."""

    def test_defaults(self) -> None:
        r = Result()
        assert r.action == Action.CONTINUE
        assert r.modified_data is None
        assert r.reason == ""

    def test_abort(self) -> None:
        r = Result(action=Action.ABORT, reason="cancelled by user")
        assert r.action == Action.ABORT
        assert r.reason == "cancelled by user"

    def test_modify(self) -> None:
        r = Result(action=Action.MODIFY, modified_data={"key": "value"})
        assert r.action == Action.MODIFY
        assert r.modified_data == {"key": "value"}


class TestHelperFactories:
    """Convenience factory functions."""

    def test_continue(self) -> None:
        r = continue_()
        assert r.action == Action.CONTINUE

    def test_abort(self) -> None:
        r = abort("nope")
        assert r.action == Action.ABORT
        assert r.reason == "nope"

    def test_modify(self) -> None:
        r = modify({"x": 1}, reason="tweaked")
        assert r.action == Action.MODIFY
        assert r.modified_data == {"x": 1}
        assert r.reason == "tweaked"


class TestRegistry:
    """Registry subscribe / emit."""

    def test_emit_no_handlers(self) -> None:
        reg = Registry()
        result = reg.emit(PingEvent(value="test"))
        assert result.action == Action.CONTINUE

    def test_handler_called(self) -> None:
        calls: list[Event] = []

        def handler(event: Event) -> Result:
            calls.append(event)
            return Result()

        reg = Registry()
        reg.on(PING, handler)
        reg.emit(PingEvent(value="hello"))
        assert len(calls) == 1
        assert isinstance(calls[0], PingEvent)

    def test_multiple_handlers_sequential(self) -> None:
        order: list[str] = []

        def first(event: Event) -> Result:
            order.append("first")
            return Result()

        def second(event: Event) -> Result:
            order.append("second")
            return Result()

        reg = Registry()
        reg.on(PING, first)
        reg.on(PING, second)
        reg.emit(PingEvent(value="test"))
        assert order == ["first", "second"]

    def test_abort_short_circuits(self) -> None:
        order: list[str] = []

        def aborter(event: Event) -> Result:
            order.append("aborter")
            return Result(action=Action.ABORT, reason="stop")

        def after_abort(event: Event) -> Result:
            order.append("after_abort")
            return Result()

        reg = Registry()
        reg.on(PING, aborter)
        reg.on(PING, after_abort)
        result = reg.emit(PingEvent(value="test"))
        assert result.action == Action.ABORT
        assert result.reason == "stop"
        assert order == ["aborter"]

    def test_modify_chains(self) -> None:
        def first_mod(event: Event) -> Result:
            return Result(action=Action.MODIFY, modified_data={"step": 1})

        def second_mod(event: Event) -> Result:
            return Result(action=Action.MODIFY, modified_data={"step": 2})

        reg = Registry()
        reg.on(PONG, first_mod)
        reg.on(PONG, second_mod)
        result = reg.emit(PongEvent(count=1))
        assert result.action == Action.MODIFY
        assert result.modified_data == {"step": 2}

    def test_unsubscribe(self) -> None:
        calls: list[int] = []

        def handler(event: Event) -> Result:
            calls.append(1)
            return Result()

        reg = Registry()
        unsub = reg.on(PONG, handler)
        reg.emit(PongEvent())
        assert len(calls) == 1

        unsub()
        reg.emit(PongEvent())
        assert len(calls) == 1  # not called again

    def test_unsubscribe_idempotent(self) -> None:
        reg = Registry()
        unsub = reg.on(PING, lambda e: Result())
        unsub()
        unsub()  # should not raise

    def test_has_handlers(self) -> None:
        reg = Registry()
        assert reg.has_handlers(PING) is False
        reg.on(PING, lambda e: Result())
        assert reg.has_handlers(PING) is True

    def test_clear_specific(self) -> None:
        reg = Registry()
        reg.on(PING, lambda e: Result())
        reg.on(PONG, lambda e: Result())
        reg.clear(PING)
        assert reg.has_handlers(PING) is False
        assert reg.has_handlers(PONG) is True

    def test_clear_all(self) -> None:
        reg = Registry()
        reg.on(PING, lambda e: Result())
        reg.on(PONG, lambda e: Result())
        reg.clear()
        assert reg.has_handlers(PING) is False
        assert reg.has_handlers(PONG) is False

    def test_different_event_types_isolated(self) -> None:
        ping_calls: list[int] = []
        pong_calls: list[int] = []

        reg = Registry()
        reg.on(PING, lambda e: (ping_calls.append(1), Result())[1])
        reg.on(PONG, lambda e: (pong_calls.append(1), Result())[1])

        reg.emit(PingEvent(value="test"))
        assert len(ping_calls) == 1
        assert len(pong_calls) == 0

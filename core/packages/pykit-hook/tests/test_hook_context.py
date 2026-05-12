"""Context-aware hook tests."""

from __future__ import annotations

from dataclasses import dataclass

from pykit_hook import Registry, abort_with_error, continue_with_error

PING = "ping"


@dataclass(frozen=True)
class PingEvent:
    type: str = PING


class TestHookContext:
    def test_emit_passes_context_to_context_handler(self) -> None:
        registry = Registry()
        seen: list[dict[str, object] | object | None] = []

        def handler(context: dict[str, object] | object | None, event: PingEvent):
            seen.append(context)
            return continue_with_error(RuntimeError(event.type))

        registry.on(PING, handler)
        result = registry.emit(PingEvent(), {"request_id": "abc"})

        assert seen == [{"request_id": "abc"}]
        assert isinstance(result.error, RuntimeError)
        assert str(result.error) == PING

    def test_emit_supports_event_only_handlers(self) -> None:
        registry = Registry()
        seen: list[str] = []

        def handler(event: PingEvent):
            seen.append(event.type)
            return abort_with_error(RuntimeError("stop"))

        registry.on(PING, handler)
        result = registry.emit(PingEvent(), object())

        assert seen == [PING]
        assert result.action.value == "abort"
        assert str(result.error) == "stop"

    def test_emit_converts_handler_exception_and_continues(self) -> None:
        registry = Registry()
        calls: list[str] = []

        def failing(event: PingEvent):
            calls.append(f"fail:{event.type}")
            raise RuntimeError("boom")

        def after(context: dict[str, object] | object | None, event: PingEvent):
            calls.append(f"after:{event.type}")
            return continue_with_error(ValueError("still running"))

        registry.on(PING, failing)
        registry.on(PING, after)
        result = registry.emit(PingEvent(), {"phase": "test"})

        assert calls == ["fail:ping", "after:ping"]
        assert isinstance(result.error, ValueError)
        assert str(result.error) == "still running"

"""Lifecycle hook management backed by ``pykit_hook.Registry``."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pykit_hook import Action, EventType, HookContext, Registry, Result, continue_

_EVENT_CONFIGURE: EventType = "lifecycle.configure"
EVENT_START: EventType = "lifecycle.start"
EVENT_READY: EventType = "lifecycle.ready"
EVENT_STOP: EventType = "lifecycle.stop"


@dataclass(frozen=True)
class LifecycleEvent:
    """Lifecycle event emitted through the hook registry."""

    type: EventType
    app_name: str


type Hook = (
    Callable[[], Awaitable[None]]
    | Callable[[LifecycleEvent], Awaitable[None]]
    | Callable[[HookContext | None, LifecycleEvent], Awaitable[None]]
)


class Lifecycle:
    """Manages ordered configure, start, ready, and stop hooks.

    Configure, start, and ready hooks execute in registration order.
    Stop hooks execute in reverse registration order so that resources
    are torn down in the opposite order they were set up.
    """

    def __init__(self, registry: Registry | None = None) -> None:
        self._registry = registry or Registry()

    @property
    def registry(self) -> Registry:
        """Return the underlying hook registry."""
        return self._registry

    def on_configure(self, hook: Hook) -> Callable[[], None]:
        """Register a hook to run during the configure phase."""
        return self._registry.on(_EVENT_CONFIGURE, self._wrap(hook))

    def on_start(self, hook: Hook) -> Callable[[], None]:
        """Register a hook to run during the start phase."""
        return self._registry.on(EVENT_START, self._wrap(hook))

    def on_ready(self, hook: Hook) -> Callable[[], None]:
        """Register a hook to run after the ready check passes."""
        return self._registry.on(EVENT_READY, self._wrap(hook))

    def on_stop(self, hook: Hook) -> Callable[[], None]:
        """Register a hook to run during shutdown."""
        return self._registry.on(EVENT_STOP, self._wrap(hook))

    async def run_configure_hooks(
        self,
        *,
        app_name: str = "",
        context: HookContext | None = None,
    ) -> None:
        """Run all configure hooks in registration order."""
        await self._emit(LifecycleEvent(type=_EVENT_CONFIGURE, app_name=app_name), context=context)

    async def run_start_hooks(
        self,
        *,
        app_name: str = "",
        context: HookContext | None = None,
    ) -> None:
        """Run all start hooks in registration order."""
        await self._emit(LifecycleEvent(type=EVENT_START, app_name=app_name), context=context)

    async def run_ready_hooks(
        self,
        *,
        app_name: str = "",
        context: HookContext | None = None,
    ) -> None:
        """Run all ready hooks in registration order."""
        await self._emit(LifecycleEvent(type=EVENT_READY, app_name=app_name), context=context)

    async def run_stop_hooks(
        self,
        *,
        app_name: str = "",
        context: HookContext | None = None,
    ) -> None:
        """Run all stop hooks in reverse registration order."""
        await self._emit(
            LifecycleEvent(type=EVENT_STOP, app_name=app_name),
            context=context,
            reverse=True,
        )

    async def _emit(
        self,
        event: LifecycleEvent,
        *,
        context: HookContext | None = None,
        reverse: bool = False,
    ) -> None:
        result = await self._registry.emit_async(event, context, reverse=reverse)
        self._raise_for_result(result)

    @staticmethod
    def _raise_for_result(result: Result) -> None:
        if result.action == Action.ABORT:
            if result.error is not None:
                raise result.error
            raise RuntimeError(result.reason or "hook execution aborted")
        if result.error is not None:
            raise result.error

    @staticmethod
    def _wrap(hook: Hook) -> Callable[[HookContext | None, LifecycleEvent], Awaitable[Result]]:
        async def handler(context: HookContext | None, event: LifecycleEvent) -> Result:
            await Lifecycle._invoke_hook(hook, context, event)
            return continue_()

        return handler

    @staticmethod
    async def _invoke_hook(hook: Hook, context: HookContext | None, event: LifecycleEvent) -> None:
        signature = inspect.signature(hook)
        positional = [
            parameter
            for parameter in signature.parameters.values()
            if parameter.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
        ]
        # Dynamic dispatch based on handler arity — call with appropriate args.
        fn: Callable[..., Awaitable[None]] = hook
        if any(
            parameter.kind == inspect.Parameter.VAR_POSITIONAL for parameter in signature.parameters.values()
        ):
            await fn(context, event)
            return
        if len(positional) >= 2:
            await fn(context, event)
            return
        if len(positional) == 1:
            await fn(event)
            return
        await fn()

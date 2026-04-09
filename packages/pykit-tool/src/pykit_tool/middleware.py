"""Middleware — composable wrappers for callable tools."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable as CallableFn
from typing import Any

from pykit_schema import ValidationResult
from pykit_tool.callable import Callable
from pykit_tool.context import Context
from pykit_tool.definition import Definition
from pykit_tool.result import Result, error_result

# Middleware is a function that wraps a Callable.
type Middleware = CallableFn[[Callable], Callable]


def chain(*middlewares: Middleware) -> Middleware:
    """Compose multiple middlewares into a single middleware.

    Middlewares are applied in order: first middleware is outermost.

    Example::

        combined = chain(with_logging(), with_timeout(5.0))
        wrapped = combined(my_tool)
    """

    def composed(tool: Callable) -> Callable:
        result = tool
        for mw in reversed(middlewares):
            result = mw(result)
        return result

    return composed


def with_logging(logger: logging.Logger | None = None) -> Middleware:
    """Middleware that logs tool calls and their duration."""
    log = logger or logging.getLogger("pykit_tool")

    def middleware(tool: Callable) -> Callable:
        return _LoggingWrapper(tool, log)

    return middleware


def with_timeout(seconds: float) -> Middleware:
    """Middleware that enforces a timeout on tool execution."""

    def middleware(tool: Callable) -> Callable:
        return _TimeoutWrapper(tool, seconds)

    return middleware


def with_validation() -> Middleware:
    """Middleware that validates input before execution."""

    def middleware(tool: Callable) -> Callable:
        return _ValidationWrapper(tool)

    return middleware


def with_result_limit(max_bytes: int) -> Middleware:
    """Middleware that truncates large results."""

    def middleware(tool: Callable) -> Callable:
        return _ResultLimitWrapper(tool, max_bytes)

    return middleware


class _LoggingWrapper:
    """Logs tool invocations."""

    def __init__(self, inner: Callable, logger: logging.Logger) -> None:
        self._inner = inner
        self._logger = logger

    @property
    def definition(self) -> Definition:
        return self._inner.definition

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        return self._inner.validate(input_data)

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        name = self.definition.name
        self._logger.info("tool.call.start: %s", name)
        start = time.monotonic()
        try:
            result = await self._inner.call(ctx, input_data)
            elapsed = time.monotonic() - start
            self._logger.info("tool.call.done: %s (%.3fs)", name, elapsed)
            return result
        except Exception:
            elapsed = time.monotonic() - start
            self._logger.exception("tool.call.error: %s (%.3fs)", name, elapsed)
            raise


class _TimeoutWrapper:
    """Enforces a timeout on tool execution."""

    def __init__(self, inner: Callable, seconds: float) -> None:
        self._inner = inner
        self._seconds = seconds

    @property
    def definition(self) -> Definition:
        return self._inner.definition

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        return self._inner.validate(input_data)

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        return await asyncio.wait_for(
            self._inner.call(ctx, input_data),
            timeout=self._seconds,
        )


class _ValidationWrapper:
    """Validates input before execution."""

    def __init__(self, inner: Callable) -> None:
        self._inner = inner

    @property
    def definition(self) -> Definition:
        return self._inner.definition

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        return self._inner.validate(input_data)

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        vr = self._inner.validate(input_data)
        if not vr.valid:
            msgs = "; ".join(f"{e.path}: {e.message}" for e in vr.errors)
            return error_result(f"validation failed: {msgs}")
        return await self._inner.call(ctx, input_data)


class _ResultLimitWrapper:
    """Truncates large results."""

    def __init__(self, inner: Callable, max_bytes: int) -> None:
        self._inner = inner
        self._max_bytes = max_bytes

    @property
    def definition(self) -> Definition:
        return self._inner.definition

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        return self._inner.validate(input_data)

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        result = await self._inner.call(ctx, input_data)
        text = result.text()
        if len(text.encode()) > self._max_bytes:
            truncated = text.encode()[: self._max_bytes].decode(errors="ignore")
            result.content = truncated + "... [truncated]"
            result.set_meta("truncated", True)
        return result

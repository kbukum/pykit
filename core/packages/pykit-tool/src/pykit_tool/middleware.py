"""Tool-domain callable composition.

Local logging, timeout, validation, result-limit, retry, and metrics middleware
were intentionally removed. Compose std/structlog logging, ``asyncio.wait_for``,
``pykit-resilience``, ``pykit-schema``, ``pykit-security``, and
``pykit-observability`` at the orchestration boundary instead.
"""

from __future__ import annotations

from collections.abc import Callable as CallableFn

from pykit_tool.callable import Callable

# Middleware is a pure callable wrapper; concrete policies live in canonical owners.

Middleware = CallableFn[[Callable], Callable]


def chain(*middlewares: Middleware) -> Middleware:
    """Compose multiple tool-domain wrappers into a single wrapper."""

    def composed(tool: Callable) -> Callable:
        result = tool
        for middleware in reversed(middlewares):
            result = middleware(result)
        return result

    return composed

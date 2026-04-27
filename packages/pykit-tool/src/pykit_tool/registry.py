"""Registry — concurrent-safe collection of callable tools."""

from __future__ import annotations

import asyncio
import builtins
import threading
from typing import Any

from pykit_tool.callable import Callable
from pykit_tool.context import Context
from pykit_tool.definition import Definition
from pykit_tool.result import Result, error_result


class Registry:
    """Thread-safe registry of callable tools.

    Example::

        registry = Registry()
        registry.register(my_tool.as_callable())
        result = await registry.call("my_tool", Context(), {"query": "test"})
    """

    def __init__(self) -> None:
        self._tools: dict[str, Callable] = {}
        self._lock = threading.RLock()

    def register(self, tool: Callable) -> None:
        """Register a tool. Raises ValueError on duplicate names."""
        name = tool.definition.name
        with self._lock:
            if name in self._tools:
                msg = f"tool already registered: {name!r}"
                raise ValueError(msg)
            self._tools[name] = tool

    def get(self, name: str) -> Callable | None:
        """Get a tool by name, or None if not found."""
        with self._lock:
            return self._tools.get(name)

    def list(self) -> list[Definition]:
        """List all registered tool definitions."""
        with self._lock:
            return [t.definition for t in self._tools.values()]

    def names(self) -> builtins.list[str]:
        """List all registered tool names."""
        with self._lock:
            return list(self._tools.keys())

    def search(self, query: str) -> builtins.list[Definition]:
        """Search tools by name or description substring (case-insensitive)."""
        q = query.lower()
        with self._lock:
            return [
                t.definition
                for t in self._tools.values()
                if q in t.definition.name.lower() or q in t.definition.description.lower()
            ]

    def filter_by_execution_hint(self, hint: str) -> builtins.list[Definition]:
        """Return tools whose annotations match the given execution_hint.

        An empty *hint* on annotations is treated as ``"backend"`` for
        backward compatibility, so ``filter_by_execution_hint("backend")``
        also returns tools that never set the field.
        """
        with self._lock:
            results: list[Definition] = []
            for t in self._tools.values():
                ann = t.definition.annotations
                effective = (ann.execution_hint or "backend") if ann else "backend"
                if effective == hint:
                    results.append(t.definition)
            return results

    async def call(self, name: str, ctx: Context, input_data: dict[str, Any]) -> Result:
        """Call a tool by name. Raises KeyError if not found."""
        tool = self.get(name)
        if tool is None:
            msg = f"tool not found: {name!r}"
            raise KeyError(msg)
        return await tool.call(ctx, input_data)

    async def call_batch(
        self,
        calls: builtins.list[tuple[str, dict[str, Any]]],
        ctx: Context,
    ) -> builtins.list[Result]:
        """Execute multiple tool calls.

        Read-only tools run concurrently; non-read-only tools run serially.
        """
        read_only: list[tuple[int, str, dict[str, Any]]] = []
        mutating: list[tuple[int, str, dict[str, Any]]] = []

        for i, (name, input_data) in enumerate(calls):
            tool = self.get(name)
            if tool is None:
                mutating.append((i, name, input_data))
                continue
            if tool.definition.read_only:
                read_only.append((i, name, input_data))
            else:
                mutating.append((i, name, input_data))

        results: list[tuple[int, Result]] = []

        # Run read-only tools concurrently.
        if read_only:

            async def _run(idx: int, n: str, inp: dict[str, Any]) -> tuple[int, Result]:
                try:
                    return (idx, await self.call(n, ctx, inp))
                except KeyError:
                    return (idx, error_result(f"tool not found: {n!r}"))
                except Exception as exc:
                    return (idx, error_result(str(exc)))

            concurrent = await asyncio.gather(
                *[_run(i, n, inp) for i, n, inp in read_only], return_exceptions=True
            )
            for item in concurrent:
                if isinstance(item, BaseException):
                    # Should not happen since _run catches all exceptions,
                    # but handle cancellation/system errors defensively.
                    results.append((len(results), error_result(str(item))))
                else:
                    results.append(item)

        # Run mutating tools serially.
        for idx, name, input_data in mutating:
            try:
                result = await self.call(name, ctx, input_data)
            except KeyError:
                result = error_result(f"tool not found: {name!r}")
            results.append((idx, result))

        # Return in original order.
        results.sort(key=lambda x: x[0])
        return [r for _, r in results]

    def __len__(self) -> int:
        with self._lock:
            return len(self._tools)

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._tools

"""@tool() decorator — auto-wire functions into Tool instances."""

from __future__ import annotations

import asyncio
import contextlib
import functools
import inspect
from collections.abc import Callable
from typing import Any

from pykit_schema import from_function
from pykit_tool.context import Context
from pykit_tool.definition import Annotations, Definition
from pykit_tool.tool import Tool


def tool(
    name: str | None = None,
    description: str | None = None,
    annotations: Annotations | None = None,
    read_only: bool = False,
    destructive: bool = False,
    timeout: float = 0.0,
    max_result_size: int = 0,
) -> Callable:
    """Decorator that converts a typed function into a Tool.

    The function can be sync or async. Sync functions are wrapped in
    an async shim automatically. The first parameter named ``ctx`` is
    treated as the execution Context and excluded from schema generation.

    Args:
        name: Tool name (defaults to function name).
        description: Tool description (defaults to docstring first line).
        annotations: Optional behavioral hints.
        read_only: Whether the tool only reads data.
        destructive: Whether the tool may cause irreversible changes.
        timeout: Default timeout in seconds.
        max_result_size: Maximum result size in bytes.

    Returns:
        A decorator that wraps the function as a ``Tool``.

    Example::

        @tool(description="Search the web")
        async def search(ctx: Context, query: str, max_results: int = 10) -> list[str]:
            return [f"Result for {query}"]

        # search is now a Tool instance with auto-generated schemas
        print(search.definition.name)  # "search"
    """

    def decorator(fn: Callable) -> Tool:
        tool_name = name or fn.__name__
        tool_desc = description
        if tool_desc is None:
            tool_desc = ""
            if fn.__doc__:
                tool_desc = fn.__doc__.strip().split("\n")[0].strip()

        input_schema = from_function(fn)

        defn = Definition(
            name=tool_name,
            description=tool_desc,
            input_schema=input_schema,
            annotations=annotations,
            read_only=read_only,
            destructive=destructive,
            timeout=timeout,
            max_result_size=max_result_size,
        )

        # Determine input type from first non-skip parameter.
        skip = {"self", "cls", "ctx", "context"}
        sig = inspect.signature(fn)
        hints = {}
        with contextlib.suppress(Exception):
            hints = dict(inspect.get_annotations(fn, eval_str=True).items())

        input_type = None
        params = [p for p in sig.parameters if p not in skip]
        if len(params) == 1:
            input_type = hints.get(params[0])

        # Check if the function accepts a ctx parameter.
        has_ctx = any(p in sig.parameters for p in ("ctx", "context"))

        # Wrap sync functions as async.
        if asyncio.iscoroutinefunction(fn):
            handler = fn
        else:

            @functools.wraps(fn)
            async def handler(*args: Any, **kwargs: Any) -> Any:
                return fn(*args, **kwargs)

        # Build the handler that accepts (ctx, input_data).
        @functools.wraps(fn)
        async def _handler(ctx: Context, input_data: Any) -> Any:
            if isinstance(input_data, dict):
                if has_ctx:
                    return await handler(ctx=ctx, **input_data)
                return await handler(**input_data)
            # If input is a Pydantic model, convert to dict for kwargs.
            from pydantic import BaseModel

            if isinstance(input_data, BaseModel):
                kwargs = input_data.model_dump()
                if has_ctx:
                    return await handler(ctx=ctx, **kwargs)
                return await handler(**kwargs)
            if has_ctx:
                return await handler(ctx, input_data)
            return await handler(input_data)

        result = Tool(
            _definition=defn,
            _handler=_handler,
            _input_type=input_type,
        )

        # Preserve original function metadata for introspection.
        functools.update_wrapper(result, fn)

        return result

    return decorator

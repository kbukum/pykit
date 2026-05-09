"""Typed tool — Tool[In, Out] with handler and schema auto-wiring."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from pykit_ai import JsonValue
from pykit_schema import ValidationResult, validate
from pykit_tool.context import Context
from pykit_tool.definition import Annotations, Definition
from pykit_tool.result import Result

JsonObject = dict[str, JsonValue]


class ToolExecutionError(RuntimeError):
    """Typed wrapper for unexpected tool execution failures."""


@dataclass
class Tool[In, Out]:
    """A typed, executable tool with auto-generated schemas.

    Wraps a handler function with metadata and JSON Schema. Typically
    created via the ``@tool()`` decorator or ``Tool.from_func()``.

    Attributes:
        _definition: Tool metadata and schemas.
        _handler: The async function that implements the tool.
        _input_type: The input type for deserialization.
    """

    _definition: Definition
    _handler: Callable[[Context, In], Awaitable[Out | Result]]
    _input_type: type[In] | None = None

    @property
    def definition(self) -> Definition:
        """Return the tool's metadata."""
        return self._definition

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        """Validate input against the tool's input schema."""
        schema = self._definition.input_schema
        if not schema:
            return ValidationResult(valid=True)
        return validate(schema, input_data)

    async def call(self, ctx: Context, input_data: In) -> Result:
        """Execute the tool with typed input."""
        try:
            raw = await self._handler(ctx, input_data)
            if isinstance(raw, Result):
                return raw
            if isinstance(raw, BaseModel):
                return Result(output=raw.model_dump(), content=raw.model_dump_json())
            if isinstance(raw, (dict, list)):
                return Result(output=raw, content=json.dumps(raw))
            if isinstance(raw, str):
                return Result(content=raw)
            return Result(output=raw, content=str(raw) if raw is not None else "")
        except (asyncio.CancelledError, KeyboardInterrupt, SystemExit):
            raise
        except Exception as exc:
            raise ToolExecutionError(str(exc)) from exc

    def with_annotations(self, annotations: Annotations) -> Tool[In, Out]:
        """Return a copy with updated annotations."""
        new_def = Definition(
            name=self._definition.name,
            description=self._definition.description,
            input_schema=self._definition.input_schema,
            output_schema=self._definition.output_schema,
            annotations=annotations,
            envelope=self._definition.envelope,
        )
        return Tool(
            _definition=new_def,
            _handler=self._handler,
            _input_type=self._input_type,
        )

    def as_callable(self) -> _CallableWrapper:
        """Convert to a type-erased Callable for registries."""
        return _CallableWrapper(self)


class _CallableWrapper:
    """Wraps a typed Tool as a Callable (dict in/out)."""

    def __init__(self, tool: Tool[Any, Any]) -> None:
        self._tool = tool

    @property
    def definition(self) -> Definition:
        return self._tool.definition

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        return self._tool.validate(input_data)

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        """Deserialize input dict, call handler, return Result."""
        return await self._tool.call(ctx, input_data)

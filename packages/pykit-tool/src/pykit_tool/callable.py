"""Callable protocol — type-erased tool interface.

Callable provides a uniform interface for tools in registries
and middleware chains, regardless of their concrete input/output types.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pykit_schema import ValidationResult
from pykit_tool.context import Context
from pykit_tool.definition import Definition
from pykit_tool.result import Result


@runtime_checkable
class Callable(Protocol):
    """Type-erased tool interface for heterogeneous registries.

    All tools can be converted to a Callable via ``as_callable()``.
    Input is exchanged as a plain dict (JSON-like), output is a ``Result``.
    """

    @property
    def definition(self) -> Definition:
        """Return the tool's metadata."""
        ...

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        """Validate input against the tool's input schema."""
        ...

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        """Execute the tool with dict input and return the result."""
        ...

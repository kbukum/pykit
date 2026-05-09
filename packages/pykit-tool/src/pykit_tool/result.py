"""Structured output of a tool execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pykit_ai import ToolResultBlock


@dataclass
class Result:
    """Structured output of a tool execution.

    Attributes:
        output: JSON-serializable structured output.
        content: Human-readable content for LLM consumption.
        is_error: True if the result represents an error.
        metadata: Arbitrary metadata about the execution.
    """

    output: Any = None
    content: str = ""
    is_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def text(self) -> str:
        """Return the human-readable representation."""
        if self.content:
            return self.content
        if self.output is not None:
            return json.dumps(self.output)
        return ""

    def set_meta(self, key: str, value: Any) -> None:
        """Store a metadata value on the result."""
        self.metadata[key] = value

    def to_block(self, id: str) -> ToolResultBlock:
        """Return the shared GenAI tool-result wire block."""
        return ToolResultBlock(id=id, content=[self.text()], is_error=self.is_error)


def text_result(content: str) -> Result:
    """Create a Result with text content."""
    return Result(content=content)


def error_result(content: str) -> Result:
    """Create an error Result."""
    return Result(content=content, is_error=True)


def json_result(value: Any) -> Result:
    """Create a Result from a JSON-serializable value."""
    return Result(output=value, content=json.dumps(value))

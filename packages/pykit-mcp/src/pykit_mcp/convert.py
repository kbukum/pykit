"""Convert between pykit tool types and MCP protocol types."""

from __future__ import annotations

import contextlib
import json
from typing import Any

from mcp import types as mcp_types

from pykit_tool.definition import Annotations, Definition
from pykit_tool.result import Result


def definition_to_mcp_tool(defn: Definition, prefix: str = "") -> mcp_types.Tool:
    """Convert a pykit Definition to an MCP Tool."""
    name = f"{prefix}{defn.name}" if prefix else defn.name

    annotations: mcp_types.ToolAnnotations | None = None
    if defn.annotations is not None:
        annotations = mcp_types.ToolAnnotations(
            title=defn.annotations.title or None,
            readOnlyHint=defn.annotations.read_only_hint,
            destructiveHint=defn.annotations.destructive_hint,
            idempotentHint=defn.annotations.idempotent_hint,
            openWorldHint=defn.annotations.open_world_hint,
        )

    input_schema = defn.input_schema or {"type": "object", "properties": {}}

    return mcp_types.Tool(
        name=name,
        description=defn.description or None,
        inputSchema=input_schema,
        annotations=annotations,
    )


def mcp_tool_to_definition(tool: mcp_types.Tool, prefix: str = "") -> Definition:
    """Convert an MCP Tool to a pykit Definition."""
    name = tool.name
    if prefix and name.startswith(prefix):
        name = name[len(prefix) :]

    annotations: Annotations | None = None
    if tool.annotations is not None:
        annotations = Annotations(
            title=tool.annotations.title or "",
            read_only_hint=tool.annotations.readOnlyHint,
            destructive_hint=tool.annotations.destructiveHint,
            idempotent_hint=tool.annotations.idempotentHint,
            open_world_hint=tool.annotations.openWorldHint,
        )

    input_schema: dict[str, Any] = {}
    if tool.inputSchema:
        input_schema = dict(tool.inputSchema)

    return Definition(
        name=name,
        description=tool.description or "",
        input_schema=input_schema,
        annotations=annotations,
    )


def result_to_mcp_result(result: Result) -> mcp_types.CallToolResult:
    """Convert a pykit Result to an MCP CallToolResult."""
    content: list[mcp_types.TextContent | mcp_types.ImageContent | mcp_types.EmbeddedResource] = []

    text = result.text()
    if text:
        content.append(mcp_types.TextContent(type="text", text=text))
    elif not content:
        content.append(mcp_types.TextContent(type="text", text=""))

    return mcp_types.CallToolResult(content=content, isError=result.is_error)


def mcp_result_to_result(mcp_result: mcp_types.CallToolResult) -> Result:
    """Convert an MCP CallToolResult to a pykit Result."""
    parts: list[str] = []
    for item in mcp_result.content:
        if isinstance(item, mcp_types.TextContent):
            parts.append(item.text)

    text = "\n".join(parts)

    # Try to parse structured output from the text.
    output: Any = None
    if text:
        with contextlib.suppress(json.JSONDecodeError, ValueError):
            output = json.loads(text)

    return Result(
        output=output,
        content=text,
        is_error=mcp_result.isError or False,
    )

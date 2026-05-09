"""Convert between pykit tool types and MCP protocol types."""

from __future__ import annotations

import contextlib
import json
from typing import Any

from mcp import types as mcp_types

from pykit_tool.definition import Annotations, Definition, Envelope, Safety
from pykit_tool.result import Result


def definition_to_mcp_tool(defn: Definition, prefix: str = "") -> mcp_types.Tool:
    """Convert a pykit Definition to an MCP Tool."""
    name = f"{prefix}{defn.name}" if prefix else defn.name
    annotations = _to_mcp_annotations(defn)
    input_schema = defn.input_schema or {"type": "object", "properties": {}}

    return mcp_types.Tool(
        name=name,
        description=defn.description or None,
        inputSchema=input_schema,
        annotations=annotations,
    )


def _to_mcp_annotations(defn: Definition) -> mcp_types.ToolAnnotations:
    safety = defn.envelope.safety
    read_only = safety == Safety.READ_ONLY
    destructive = safety == Safety.DESTRUCTIVE
    open_world = bool(defn.envelope.network.rules or defn.envelope.filesystem or defn.envelope.subprocess)
    return mcp_types.ToolAnnotations(
        title=defn.annotations.title or None,
        readOnlyHint=read_only,
        destructiveHint=destructive,
        idempotentHint=defn.annotations.idempotent_hint,
        openWorldHint=open_world,
    )


def mcp_tool_to_definition(tool: mcp_types.Tool, prefix: str = "") -> Definition:
    """Convert an MCP Tool to a pykit Definition."""
    name = tool.name
    if prefix and name.startswith(prefix):
        name = name[len(prefix) :]

    annotations = Annotations()
    if tool.annotations is not None:
        annotations = Annotations(
            title=tool.annotations.title or "",
            idempotent_hint=tool.annotations.idempotentHint,
        )

    input_schema: dict[str, Any] = {}
    if tool.inputSchema:
        input_schema = dict(tool.inputSchema)

    safety = Safety.READ_ONLY
    if tool.annotations is not None:
        if tool.annotations.readOnlyHint:
            safety = Safety.READ_ONLY
        if tool.annotations.destructiveHint:
            safety = Safety.DESTRUCTIVE

    return Definition(
        name=name,
        description=tool.description or "",
        input_schema=input_schema,
        annotations=annotations,
        envelope=Envelope(safety=safety),
    )


def result_to_mcp_result(result: Result) -> mcp_types.CallToolResult:
    """Convert a pykit Result to an MCP CallToolResult."""
    content: list[mcp_types.TextContent | mcp_types.ImageContent | mcp_types.EmbeddedResource] = []

    text = result.text()
    if text:
        content.append(mcp_types.TextContent(type="text", text=text))
    elif not content:
        content.append(mcp_types.TextContent(type="text", text=""))

    return mcp_types.CallToolResult(content=content, isError=result.is_error)  # type: ignore[arg-type]  # content list type is compatible at runtime


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

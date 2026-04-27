"""MCP server — expose a pykit ToolRegistry as an MCP server."""

from __future__ import annotations

import traceback
from typing import Any

from mcp.server import Server
from mcp.types import CallToolResult, TextContent, Tool

from pykit_mcp.convert import definition_to_mcp_tool, result_to_mcp_result
from pykit_tool.context import Context
from pykit_tool.registry import Registry


def create_server(
    name: str,
    version: str,
    registry: Registry,
    prefix: str = "",
) -> Server:
    """Create an MCP Server backed by a pykit tool registry.

    Each tool in the registry is exposed as an MCP tool. Calls are delegated
    to ``registry.call()`` and results are converted to MCP format.

    Args:
        name: Server name reported during MCP initialization.
        version: Server version reported during MCP initialization.
        registry: The pykit tool registry containing tools to expose.
        prefix: Optional prefix prepended to tool names (e.g. ``"myapp_"``).

    Returns:
        A configured ``mcp.server.Server`` ready to run.
    """
    server = Server(name)

    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]  # untyped decorator from mcp library
    async def _list_tools() -> list[Tool]:
        return [definition_to_mcp_tool(d, prefix) for d in registry.list()]

    @server.call_tool()  # type: ignore[untyped-decorator]  # untyped decorator from mcp library
    async def _call_tool(name: str, arguments: dict[str, Any] | None) -> CallToolResult:
        # Strip prefix to get the registry tool name.
        tool_name = name
        if prefix and tool_name.startswith(prefix):
            tool_name = tool_name[len(prefix) :]

        tool = registry.get(tool_name)
        if tool is None:
            return CallToolResult(
                content=[TextContent(type="text", text=f"tool not found: {tool_name!r}")],
                isError=True,
            )

        # Validate input.
        input_data = arguments or {}
        validation = tool.validate(input_data)
        if not validation.valid:
            error_text = "; ".join(str(e) for e in validation.errors)
            return CallToolResult(
                content=[TextContent(type="text", text=f"validation error: {error_text}")],
                isError=True,
            )

        try:
            ctx = Context()
            result = await registry.call(tool_name, ctx, input_data)
            return result_to_mcp_result(result)
        except Exception as exc:
            tb = traceback.format_exc()
            return CallToolResult(
                content=[TextContent(type="text", text=f"tool error: {exc}\n{tb}")],
                isError=True,
            )

    return server

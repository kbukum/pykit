"""pykit-mcp — Bridge pykit tool registry with the Model Context Protocol.

Provides converters, an MCP server backed by a pykit ToolRegistry,
and a client that wraps remote MCP tools as pykit Callables.

Usage::

    from pykit_mcp import create_server, connect

    # Server side
    server = create_server("my-server", "1.0.0", registry)

    # Client side
    tools = await connect(session, prefix="myapp_")
"""

from pykit_mcp.client import RemoteCallable, connect
from pykit_mcp.convert import (
    definition_to_mcp_tool,
    mcp_result_to_result,
    mcp_tool_to_definition,
    result_to_mcp_result,
)
from pykit_mcp.server import create_server

__all__ = [
    "RemoteCallable",
    "connect",
    "create_server",
    "definition_to_mcp_tool",
    "mcp_result_to_result",
    "mcp_tool_to_definition",
    "result_to_mcp_result",
]

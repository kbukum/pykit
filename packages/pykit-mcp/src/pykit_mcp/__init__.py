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
from pykit_mcp.server import (
    PromptEntry,
    ResourceEntry,
    ResourceTemplateEntry,
    ToolAuditEvent,
    ToolAuthorizationDecision,
    ToolAuthorizationRequest,
    create_server,
)
from pykit_mcp.transport import (
    DEFAULT_ALLOWED_HOSTS,
    TRANSPORT_STDIO,
    TRANSPORT_STREAMABLE_HTTP,
    create_mcp_http_security_config,
    create_streamable_http_security_settings,
    validate_transport_name,
)

__all__ = [
    "RemoteCallable",
    "PromptEntry",
    "ResourceEntry",
    "ResourceTemplateEntry",
    "ToolAuditEvent",
    "ToolAuthorizationDecision",
    "ToolAuthorizationRequest",
    "TRANSPORT_STDIO",
    "TRANSPORT_STREAMABLE_HTTP",
    "DEFAULT_ALLOWED_HOSTS",
    "connect",
    "create_mcp_http_security_config",
    "create_streamable_http_security_settings",
    "create_server",
    "definition_to_mcp_tool",
    "mcp_result_to_result",
    "mcp_tool_to_definition",
    "result_to_mcp_result",
    "validate_transport_name",
]

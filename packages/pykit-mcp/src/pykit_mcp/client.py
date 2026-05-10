"""MCP client — connect to an MCP server and wrap remote tools as pykit Callables."""

from __future__ import annotations

from typing import Any

from mcp import ClientSession
from mcp.types import Tool as McpTool
from opentelemetry import trace
from opentelemetry.trace import Tracer

from pykit_ai.semconv import GENAI_OPERATION_MCP_REQUEST, GENAI_OPERATION_NAME, GENAI_TOOL_NAME
from pykit_mcp.convert import mcp_result_to_result, mcp_tool_to_definition
from pykit_schema import ValidationResult, validate
from pykit_tool.callable import Callable
from pykit_tool.context import Context
from pykit_tool.definition import Definition
from pykit_tool.result import Result


class RemoteCallable:
    """A pykit Callable that delegates to a remote MCP tool via a ClientSession."""

    def __init__(
        self,
        session: ClientSession,
        mcp_tool: McpTool,
        prefix: str = "",
        server: str = "",
        *,
        tracer: Tracer | None = None,
    ) -> None:
        self._session = session
        self._definition = mcp_tool_to_definition(mcp_tool, prefix)
        self._mcp_name = mcp_tool.name
        self._mcp_server = server
        self._tracer = tracer or trace.get_tracer("pykit_mcp")

    @property
    def definition(self) -> Definition:
        return self._definition

    @property
    def mcp_server(self) -> str:
        return self._mcp_server

    @property
    def mcp_method(self) -> str:
        return "tools/call"

    def validate(self, input_data: dict[str, Any]) -> ValidationResult:
        schema = self._definition.input_schema
        if not schema:
            return ValidationResult(valid=True)
        return validate(schema, input_data)

    async def call(self, ctx: Context, input_data: dict[str, Any]) -> Result:
        """Call the remote MCP tool and convert the result."""
        with self._tracer.start_as_current_span("mcp.request") as span:
            span.set_attribute(GENAI_OPERATION_NAME, GENAI_OPERATION_MCP_REQUEST)
            span.set_attribute(GENAI_TOOL_NAME, self._definition.name)
            span.set_attribute("mcp.method", "tools/call")
            span.set_attribute("mcp.tool_name", self._mcp_name)
            if ctx.tool_use_id:
                span.set_attribute("tool.use_id", ctx.tool_use_id)
            mcp_result = await self._session.call_tool(self._mcp_name, input_data)
            return mcp_result_to_result(mcp_result)


async def connect(
    session: ClientSession,
    prefix: str = "",
    server: str = "",
    *,
    tracer: Tracer | None = None,
) -> list[Callable]:
    """Discover remote MCP tools and return them as pykit Callables.

    The session must already be initialized (via ``session.initialize()``).

    Args:
        session: An initialized MCP ClientSession.
        prefix: Optional prefix to strip from remote tool names.
        server: Optional server name for observe-only agent hooks.

    Returns:
        A list of Callable wrappers for each remote MCP tool.
    """
    result = await session.list_tools()
    callables: list[Callable] = []
    for tool in result.tools:
        callables.append(RemoteCallable(session, tool, prefix, server, tracer=tracer))
    return callables

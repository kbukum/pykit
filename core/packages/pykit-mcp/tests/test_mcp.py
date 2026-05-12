from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent, Tool

from pykit_authz import Decision, DecisionRequest
from pykit_mcp import (
    TRANSPORT_STDIO,
    TRANSPORT_STREAMABLE_HTTP,
    connect,
    create_mcp_http_security_config,
    create_server,
    create_streamable_http_security_settings,
    definition_to_mcp_tool,
    mcp_result_to_result,
    mcp_tool_to_definition,
    result_to_mcp_result,
    validate_transport_name,
)
from pykit_tool import Context, Envelope, FilesystemMode, FilesystemRule, Registry, Result, Safety, tool


@tool(description="Greet a person")
async def greet(ctx: Context, name: str) -> str:
    return f"Hello, {name}!"


def registry() -> Registry:
    reg = Registry()
    reg.register(greet.as_callable())
    return reg


class DenyDecider:
    async def decide(self, request: DecisionRequest) -> Decision:
        return Decision(False, "denied")


def test_convert_roundtrip_derives_envelope() -> None:
    mcp_tool = definition_to_mcp_tool(greet.definition)
    assert mcp_tool.annotations is not None
    assert mcp_tool.annotations.readOnlyHint is True
    assert mcp_tool.annotations.destructiveHint is False
    assert mcp_tool.annotations.openWorldHint is False

    definition = mcp_tool_to_definition(mcp_tool)
    assert definition.name == "greet"
    assert definition.envelope.safety is Safety.READ_ONLY


def test_mcp_annotations_are_synthesized_from_envelope() -> None:
    destructive = Envelope(
        safety=Safety.DESTRUCTIVE,
        filesystem=(FilesystemRule(path="/data/**", mode=FilesystemMode.DELETE),),
    )

    @tool(description="Delete data", envelope=destructive)
    async def delete_data(ctx: Context) -> str:
        return "deleted"

    mcp_tool = definition_to_mcp_tool(delete_data.definition)
    assert mcp_tool.annotations is not None
    assert mcp_tool.annotations.readOnlyHint is False
    assert mcp_tool.annotations.destructiveHint is True
    assert mcp_tool.annotations.openWorldHint is True


def test_mcp_tool_without_annotations_defaults_to_read_only() -> None:
    definition = mcp_tool_to_definition(
        Tool(name="list_tools", description="List available tools", inputSchema={"type": "object"})
    )
    assert definition.envelope.safety is Safety.READ_ONLY


def test_result_conversion() -> None:
    converted = result_to_mcp_result(Result(content="hello"))
    assert converted.content[0].text == "hello"
    back = mcp_result_to_result(CallToolResult(content=[TextContent(type="text", text='{"ok": true}')]))
    assert back.output == {"ok": True}


@pytest.mark.asyncio
async def test_server_roundtrip() -> None:
    server = create_server("test", "0.1.0", registry())
    async with create_connected_server_and_client_session(server) as session:
        tools = await session.list_tools()
        assert [tool.name for tool in tools.tools] == ["greet"]
        result = await session.call_tool("greet", {"name": "MCP"})
        assert result.content[0].text == "Hello, MCP!"


@pytest.mark.asyncio
async def test_decider_denies_tool_invocation() -> None:
    server = create_server("test", "0.1.0", registry(), decider=DenyDecider())
    async with create_connected_server_and_client_session(server) as session:
        result = await session.call_tool("greet", {"name": "MCP"})
        assert result.isError
        assert result.content[0].text == "tool call denied: denied"


@pytest.mark.asyncio
async def test_remote_tools_register_locally() -> None:
    server = create_server("test", "0.1.0", registry())
    async with create_connected_server_and_client_session(server) as session:
        callables = await connect(session)
        local = Registry()
        for callable_tool in callables:
            local.register(callable_tool)
        assert "greet" in local


def test_transport_helpers() -> None:
    assert validate_transport_name(TRANSPORT_STDIO) == TRANSPORT_STDIO
    assert validate_transport_name(TRANSPORT_STREAMABLE_HTTP) == TRANSPORT_STREAMABLE_HTTP
    with pytest.raises(ValueError):
        validate_transport_name("sse")
    settings = create_streamable_http_security_settings()
    assert settings.allowed_hosts == ["localhost", "127.0.0.1", "::1"]
    helper = create_mcp_http_security_config(max_payload_bytes=1024)
    assert helper.bind_host == "127.0.0.1"
    assert helper.require_oauth_pkce is True

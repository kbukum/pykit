"""Tests for pykit_mcp — MCP bridge for pykit tool registry."""

from __future__ import annotations

from mcp.shared.memory import create_connected_server_and_client_session

from pykit_mcp import (
    connect,
    create_server,
    definition_to_mcp_tool,
    mcp_result_to_result,
    mcp_tool_to_definition,
    result_to_mcp_result,
)
from pykit_mcp.client import RemoteCallable
from pykit_tool import Context, Registry, Result, tool

# ── Fixtures ──────────────────────────────────────────────────────────


@tool(description="Greet a person")
async def greet(ctx: Context, name: str) -> str:
    return f"Hello, {name}!"


@tool(description="Add two numbers", read_only=True)
async def add(ctx: Context, a: int, b: int) -> dict:
    return {"sum": a + b}


@tool(description="Always fails")
async def fail_tool(ctx: Context) -> Result:
    raise RuntimeError("intentional error")


@tool(description="Echo with prefix")
async def echo(ctx: Context, message: str) -> str:
    return f"echo: {message}"


def _make_registry(*tools_to_register) -> Registry:
    registry = Registry()
    for t in tools_to_register:
        registry.register(t.as_callable())
    return registry


# ── Convert tests ─────────────────────────────────────────────────────


class TestConvert:
    def test_definition_to_mcp_tool(self):
        defn = greet.definition
        mcp_tool = definition_to_mcp_tool(defn)
        assert mcp_tool.name == "greet"
        assert mcp_tool.description == "Greet a person"
        assert "name" in mcp_tool.inputSchema.get("properties", {})

    def test_definition_to_mcp_tool_with_prefix(self):
        defn = greet.definition
        mcp_tool = definition_to_mcp_tool(defn, prefix="myapp_")
        assert mcp_tool.name == "myapp_greet"

    def test_mcp_tool_to_definition(self):
        defn = greet.definition
        mcp_tool = definition_to_mcp_tool(defn)
        roundtrip = mcp_tool_to_definition(mcp_tool)
        assert roundtrip.name == "greet"
        assert roundtrip.description == "Greet a person"

    def test_mcp_tool_to_definition_strips_prefix(self):
        defn = greet.definition
        mcp_tool = definition_to_mcp_tool(defn, prefix="myapp_")
        roundtrip = mcp_tool_to_definition(mcp_tool, prefix="myapp_")
        assert roundtrip.name == "greet"

    def test_result_to_mcp_result_text(self):
        result = Result(content="hello world")
        mcp_result = result_to_mcp_result(result)
        assert not mcp_result.isError
        assert len(mcp_result.content) == 1
        assert mcp_result.content[0].text == "hello world"

    def test_result_to_mcp_result_error(self):
        result = Result(content="something broke", is_error=True)
        mcp_result = result_to_mcp_result(result)
        assert mcp_result.isError is True

    def test_mcp_result_to_result_text(self):
        from mcp.types import CallToolResult, TextContent

        mcp_result = CallToolResult(
            content=[TextContent(type="text", text="plain text")],
        )
        result = mcp_result_to_result(mcp_result)
        assert result.content == "plain text"
        assert result.is_error is False
        assert result.output is None  # not valid JSON

    def test_mcp_result_to_result_json(self):
        from mcp.types import CallToolResult, TextContent

        mcp_result = CallToolResult(
            content=[TextContent(type="text", text='{"key": "value"}')],
        )
        result = mcp_result_to_result(mcp_result)
        assert result.output == {"key": "value"}
        assert result.is_error is False


# ── Round-trip integration tests ──────────────────────────────────────


class TestRoundTrip:
    async def test_list_tools(self):
        registry = _make_registry(greet, add)
        server = create_server("test", "0.1.0", registry)

        async with create_connected_server_and_client_session(server) as session:
            result = await session.list_tools()
            names = {t.name for t in result.tools}
            assert names == {"greet", "add"}

    async def test_call_tool_text_result(self):
        registry = _make_registry(greet)
        server = create_server("test", "0.1.0", registry)

        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool("greet", {"name": "World"})
            assert not result.isError
            assert result.content[0].text == "Hello, World!"

    async def test_call_tool_json_result(self):
        registry = _make_registry(add)
        server = create_server("test", "0.1.0", registry)

        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool("add", {"a": 3, "b": 4})
            assert not result.isError
            assert '"sum": 7' in result.content[0].text

    async def test_call_tool_with_prefix(self):
        registry = _make_registry(greet)
        server = create_server("test", "0.1.0", registry, prefix="app_")

        async with create_connected_server_and_client_session(server) as session:
            # Tools should be listed with prefix.
            result = await session.list_tools()
            assert result.tools[0].name == "app_greet"

            # Calling with the prefixed name should work.
            call_result = await session.call_tool("app_greet", {"name": "MCP"})
            assert not call_result.isError
            assert "Hello, MCP!" in call_result.content[0].text

    async def test_validation_error(self):
        registry = _make_registry(greet)
        server = create_server("test", "0.1.0", registry)

        async with create_connected_server_and_client_session(server) as session:
            # 'name' is required but missing.
            result = await session.call_tool("greet", {})
            assert result.isError
            assert "validation error" in result.content[0].text

    async def test_tool_not_found(self):
        registry = _make_registry(greet)
        server = create_server("test", "0.1.0", registry)

        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool("nonexistent", {})
            assert result.isError
            assert "not found" in result.content[0].text

    async def test_tool_raises_exception(self):
        registry = _make_registry(fail_tool)
        server = create_server("test", "0.1.0", registry)

        async with create_connected_server_and_client_session(server) as session:
            result = await session.call_tool("fail_tool", {})
            assert result.isError
            assert "intentional error" in result.content[0].text


# ── Client tests (connect + RemoteCallable) ──────────────────────────


class TestClient:
    async def test_connect_returns_callables(self):
        registry = _make_registry(greet, add)
        server = create_server("test", "0.1.0", registry)

        async with create_connected_server_and_client_session(server) as session:
            callables = await connect(session)
            names = {c.definition.name for c in callables}
            assert names == {"greet", "add"}
            assert all(isinstance(c, RemoteCallable) for c in callables)

    async def test_connect_with_prefix(self):
        registry = _make_registry(echo)
        server = create_server("test", "0.1.0", registry, prefix="svc_")

        async with create_connected_server_and_client_session(server) as session:
            callables = await connect(session, prefix="svc_")
            assert len(callables) == 1
            # Prefix is stripped from the definition name.
            assert callables[0].definition.name == "echo"

    async def test_remote_callable_call(self):
        registry = _make_registry(greet)
        server = create_server("test", "0.1.0", registry)

        async with create_connected_server_and_client_session(server) as session:
            callables = await connect(session)
            greet_remote = callables[0]
            result = await greet_remote.call(Context(), {"name": "Remote"})
            assert result.content == "Hello, Remote!"
            assert not result.is_error

    async def test_remote_callable_validate(self):
        registry = _make_registry(greet)
        server = create_server("test", "0.1.0", registry)

        async with create_connected_server_and_client_session(server) as session:
            callables = await connect(session)
            greet_remote = callables[0]

            # Valid input.
            vr = greet_remote.validate({"name": "Alice"})
            assert vr.valid

            # Invalid — missing required field.
            vr2 = greet_remote.validate({})
            assert not vr2.valid

    async def test_register_remote_tools_in_local_registry(self):
        """Remote MCP tools can be registered into a local registry."""
        registry = _make_registry(greet, add)
        server = create_server("test", "0.1.0", registry)

        async with create_connected_server_and_client_session(server) as session:
            callables = await connect(session)

            local_registry = Registry()
            for c in callables:
                local_registry.register(c)

            assert "greet" in local_registry
            assert "add" in local_registry

            result = await local_registry.call("greet", Context(), {"name": "Local"})
            assert result.content == "Hello, Local!"

from __future__ import annotations

import pytest
from mcp import Client
from mcp.types import (
    GetPromptResult,
    Prompt,
    PromptArgument,
    PromptMessage,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    TextContent,
    TextResourceContents,
)

from pykit_mcp import PromptEntry, ResourceEntry, ResourceTemplateEntry, ToolAuditEvent, create_server
from pykit_tool import (
    Context,
    Definition,
    Envelope,
    Registry,
    Result,
    SensitiveMatcher,
    SensitivePredicate,
    Tool,
    tool,
)


@tool(description="Add two numbers")
async def add(ctx: Context, a: int, b: int) -> dict[str, int]:
    return {"sum": a + b}


@tool(description="Fails")
async def fail_tool(ctx: Context) -> Result:
    raise RuntimeError("intentional error")


@tool(description="Greet")
async def greet(ctx: Context, name: str) -> str:
    return f"Hello, {name}!"


def reg(*items) -> Registry:
    registry = Registry()
    for item in items:
        registry.register(item.as_callable())
    return registry


@pytest.mark.asyncio
async def test_allowed_missing_validation_and_tool_error_branches() -> None:
    server = create_server("test", "0.1.0", reg(greet, add, fail_tool), allowed_tools={"greet", "fail_tool"})
    async with Client(server) as client:
        session = client.session
        listed = await session.list_tools()
        assert {tool.name for tool in listed.tools} == {"greet", "fail_tool"}
        denied = await session.call_tool("add", {"a": 1, "b": 2})
        assert denied.is_error and "not allowed" in denied.content[0].text
        invalid = await session.call_tool("greet", {})
        assert invalid.is_error and "validation error" in invalid.content[0].text
        failed = await session.call_tool("fail_tool", {})
        assert failed.is_error and "intentional error" in failed.content[0].text

    server = create_server("test", "0.1.0", reg(greet))
    async with Client(server) as client:
        session = client.session
        missing = await session.call_tool("missing", {})
        assert missing.is_error and "not found" in missing.content[0].text


@pytest.mark.asyncio
async def test_output_schema_result_limit_and_input_limit() -> None:
    async def bad_output(ctx: Context, input_data: dict[str, object]) -> dict[str, str]:
        return {"sum": "bad"}

    invalid = Tool(
        _definition=Definition(
            name="bad_output",
            description="Return invalid output",
            input_schema={"type": "object", "properties": {}},
            output_schema={"type": "object", "properties": {"sum": {"type": "integer"}}, "required": ["sum"]},
        ),
        _handler=bad_output,
    ).as_callable()
    registry = Registry()
    registry.register(invalid)
    server = create_server("test", "0.1.0", registry, max_input_bytes=2, max_result_bytes=4)
    async with Client(server) as client:
        session = client.session
        too_large = await session.call_tool("bad_output", {"x": "toolong"})
        assert too_large.is_error and "input too large" in too_large.content[0].text

    server = create_server("test", "0.1.0", registry)
    async with Client(server) as client:
        session = client.session
        invalid_output = await session.call_tool("bad_output", {})
        assert invalid_output.is_error and "output validation error" in invalid_output.content[0].text


@pytest.mark.asyncio
async def test_prompts_resources_templates_handlers() -> None:
    server = create_server(
        "test",
        "0.1.0",
        Registry(),
        prompts=[
            PromptEntry(
                prompt=Prompt(name="greet", arguments=[PromptArgument(name="name", required=True)]),
                handler=lambda arguments: GetPromptResult(
                    messages=[
                        PromptMessage(
                            role="user",
                            content=TextContent(type="text", text=f"Say hello to {arguments['name']}"),
                        )
                    ]
                ),
            )
        ],
        resources=[
            ResourceEntry(
                resource=Resource(uri="memo://info", name="info", mime_type="text/plain"),
                handler=lambda uri: ReadResourceResult(
                    contents=[TextResourceContents(uri=uri, mime_type="text/plain", text="info")]
                ),
            )
        ],
        resource_templates=[
            ResourceTemplateEntry(
                resource_template=ResourceTemplate(uri_template="memo://items/{id}", name="item"),
                handler=lambda uri: ReadResourceResult(
                    contents=[TextResourceContents(uri=uri, mime_type="text/plain", text=f"templated:{uri}")]
                ),
            )
        ],
    )
    async with Client(server) as client:
        session = client.session
        prompts = await session.list_prompts()
        assert [prompt.name for prompt in prompts.prompts] == ["greet"]
        prompt = await session.get_prompt("greet", {"name": "World"})
        assert prompt.messages[0].content.text == "Say hello to World"
        resources = await session.list_resources()
        assert [str(resource.uri) for resource in resources.resources] == ["memo://info"]
        templates = await session.list_resource_templates()
        assert [template.uri_template for template in templates.resource_templates] == ["memo://items/{id}"]
        resource = await session.read_resource("memo://info")
        assert resource.contents[0].text == "info"
        templated = await session.read_resource("memo://items/123")
        assert templated.contents[0].text == "templated:memo://items/123"


@pytest.mark.asyncio
async def test_sensitivity_denial_is_tool_result_and_version_is_reported() -> None:
    sensitive = Envelope(
        sensitive_invocations=(SensitivePredicate(jsonpath="name", matcher=SensitiveMatcher.EXISTS),),
    )

    @tool(description="Greet sensitively", envelope=sensitive)
    async def guarded(ctx: Context, name: str) -> str:
        return f"Hello, {name}!"

    events: list[ToolAuditEvent] = []
    server = create_server("test", "1.2.3", reg(guarded), tool_audit_sink=events.append)
    async with Client(server) as client:
        assert client.server_info is not None
        assert client.server_info.version == "1.2.3"
        denied = await client.session.call_tool("guarded", {"name": "MCP"})
    assert denied.is_error
    assert denied.content[0].text == "tool call denied: sensitive invocation denied: 'guarded'"
    assert [event.outcome for event in events] == ["denied"]

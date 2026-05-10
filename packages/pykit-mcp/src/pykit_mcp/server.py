"""MCP server — expose a pykit ToolRegistry as an MCP server."""

from __future__ import annotations

import inspect
import json
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass

import mcp.types as mcp_types
from mcp.server import Server
from mcp.types import (
    CallToolResult,
    GetPromptRequestParams,
    GetPromptResult,
    ListPromptsResult,
    ListResourcesResult,
    ListResourceTemplatesResult,
    Prompt,
    ReadResourceRequestParams,
    ReadResourceResult,
    Resource,
    ResourceTemplate,
    TextContent,
    Tool,
)
from opentelemetry import trace
from opentelemetry.trace import Tracer

from pykit_ai import JsonValue
from pykit_ai.semconv import GENAI_OPERATION_MCP_REQUEST, GENAI_OPERATION_NAME, GENAI_TOOL_NAME
from pykit_authz import Decider, DecisionRequest
from pykit_mcp.convert import definition_to_mcp_tool, result_to_mcp_result
from pykit_schema import ValidationResult, validate
from pykit_tool.context import Context
from pykit_tool.definition import Definition
from pykit_tool.registry import Registry
from pykit_tool.result import Result

JsonObject = dict[str, JsonValue]

ToolAuthorizer = Callable[
    ["ToolAuthorizationRequest"],
    "ToolAuthorizationDecision | bool | Awaitable[ToolAuthorizationDecision | bool]",
]
ToolAuditSink = Callable[["ToolAuditEvent"], "None | Awaitable[None]"]
PromptHandler = Callable[
    [dict[str, str]],
    "GetPromptResult | Awaitable[GetPromptResult]",
]
ResourceHandler = Callable[
    [str],
    "ReadResourceResult | Awaitable[ReadResourceResult]",
]


@dataclass(frozen=True, slots=True)
class ToolAuthorizationRequest:
    """MCP tool invocation authorization input."""

    tool_name: str
    mcp_name: str
    arguments: JsonObject


@dataclass(frozen=True, slots=True)
class ToolAuthorizationDecision:
    """MCP tool authorization decision."""

    allowed: bool
    reason: str = ""


@dataclass(frozen=True, slots=True)
class ToolAuditEvent:
    """Final MCP tool invocation outcome."""

    tool_name: str
    mcp_name: str
    outcome: str
    reason: str = ""
    error: str = ""


@dataclass(frozen=True, slots=True)
class PromptEntry:
    """Static MCP prompt registration."""

    prompt: Prompt
    handler: PromptHandler


@dataclass(frozen=True, slots=True)
class ResourceEntry:
    """Static MCP resource registration."""

    resource: Resource
    handler: ResourceHandler


@dataclass(frozen=True, slots=True)
class ResourceTemplateEntry:
    """Static MCP resource-template registration."""

    resource_template: ResourceTemplate
    handler: ResourceHandler


def create_server(
    name: str,
    version: str,
    registry: Registry,
    prefix: str = "",
    allowed_tools: Iterable[str] | None = None,
    tool_authorizer: ToolAuthorizer | None = None,
    tool_audit_sink: ToolAuditSink | None = None,
    decider: Decider | None = None,
    max_input_bytes: int = 0,
    max_result_bytes: int = 0,
    prompts: Iterable[PromptEntry] | None = None,
    resources: Iterable[ResourceEntry] | None = None,
    resource_templates: Iterable[ResourceTemplateEntry] | None = None,
    tracer: Tracer | None = None,
) -> Server:
    """Create an MCP Server backed by a pykit tool registry.

    Each tool in the registry is exposed as an MCP tool. Calls are delegated
    to ``registry.call()`` and results are converted to MCP format.

    Args:
        name: Server name reported during MCP initialization.
        version: Server version reported during MCP initialization.
        registry: The pykit tool registry containing tools to expose.
        prefix: Optional prefix prepended to tool names (e.g. ``"myapp_"``).
        allowed_tools: Optional registry tool-name allow-list. When omitted,
            all registered tools are exposed.
        tool_authorizer: Optional per-call authorization hook.
        tool_audit_sink: Optional sink that records every tool invocation outcome.
        decider: Optional pykit-authz decider for per-invocation enforcement.
        max_input_bytes: Reject calls whose JSON arguments exceed this size.
        max_result_bytes: Reject results whose serialized output exceeds this size.
        prompts: Optional static MCP prompt registrations.
        resources: Optional static MCP resource registrations.
        resource_templates: Optional static MCP resource-template registrations.

    Returns:
        A configured ``mcp.server.Server`` ready to run.
    """
    if max_input_bytes < 0:
        raise ValueError("max_input_bytes must be >= 0")
    if max_result_bytes < 0:
        raise ValueError("max_result_bytes must be >= 0")
    prompt_entries = tuple(prompts or ())
    otel_tracer = tracer or trace.get_tracer("pykit_mcp")
    resource_entries = tuple(resources or ())
    resource_template_entries = tuple(resource_templates or ())
    prompt_map = {entry.prompt.name: entry for entry in prompt_entries}
    resource_map = {str(entry.resource.uri): entry for entry in resource_entries}

    async def _list_prompts(_ctx: object, _params: object) -> ListPromptsResult:
        return ListPromptsResult(prompts=[entry.prompt for entry in prompt_entries])

    async def _get_prompt(_ctx: object, params: GetPromptRequestParams) -> GetPromptResult:
        entry = prompt_map.get(params.name)
        if entry is None:
            raise ValueError(f"prompt not found: {params.name}")
        return await _await_if_needed(entry.handler(dict(params.arguments or {})))

    async def _list_resources(_ctx: object, _params: object) -> ListResourcesResult:
        return ListResourcesResult(resources=[entry.resource for entry in resource_entries])

    async def _list_resource_templates(_ctx: object, _params: object) -> ListResourceTemplatesResult:
        return ListResourceTemplatesResult(
            resourceTemplates=[entry.resource_template for entry in resource_template_entries]
        )

    async def _read_resource(_ctx: object, params: ReadResourceRequestParams) -> ReadResourceResult:
        uri = str(params.uri)
        if uri in resource_map:
            return await _await_if_needed(resource_map[uri].handler(uri))
        for entry in resource_template_entries:
            if _resource_template_matches(entry.resource_template.uriTemplate, uri):
                return await _await_if_needed(entry.handler(uri))
        raise ValueError(f"resource not found: {uri}")

    server = Server(name)
    if prompt_entries:

        async def _handle_list_prompts(_request: mcp_types.ListPromptsRequest) -> mcp_types.ServerResult:
            return mcp_types.ServerResult(await _list_prompts(None, None))

        async def _handle_get_prompt(request: mcp_types.GetPromptRequest) -> mcp_types.ServerResult:
            return mcp_types.ServerResult(await _get_prompt(None, request.params))

        server.request_handlers[mcp_types.ListPromptsRequest] = _handle_list_prompts
        server.request_handlers[mcp_types.GetPromptRequest] = _handle_get_prompt
    if resource_entries:

        async def _handle_list_resources(_request: mcp_types.ListResourcesRequest) -> mcp_types.ServerResult:
            return mcp_types.ServerResult(await _list_resources(None, None))

        server.request_handlers[mcp_types.ListResourcesRequest] = _handle_list_resources
    if resource_template_entries:

        async def _handle_list_resource_templates(
            _request: mcp_types.ListResourceTemplatesRequest,
        ) -> mcp_types.ServerResult:
            return mcp_types.ServerResult(await _list_resource_templates(None, None))

        server.request_handlers[mcp_types.ListResourceTemplatesRequest] = _handle_list_resource_templates
    if resource_entries or resource_template_entries:

        async def _handle_read_resource(request: mcp_types.ReadResourceRequest) -> mcp_types.ServerResult:
            return mcp_types.ServerResult(await _read_resource(None, request.params))

        server.request_handlers[mcp_types.ReadResourceRequest] = _handle_read_resource
    allowed = set(allowed_tools or ())

    def is_allowed(tool_name: str) -> bool:
        return not allowed or tool_name in allowed

    @server.list_tools()  # type: ignore[no-untyped-call, untyped-decorator]  # untyped decorator from mcp library
    async def _list_tools() -> list[Tool]:
        return [definition_to_mcp_tool(d, prefix) for d in registry.list() if is_allowed(d.name)]

    @server.call_tool()  # type: ignore[untyped-decorator]  # untyped decorator from mcp library
    async def _call_tool(name: str, arguments: JsonObject | None) -> CallToolResult:
        with otel_tracer.start_as_current_span("mcp.request") as span:
            # Strip prefix to get the registry tool name.
            tool_name = name
            if prefix and tool_name.startswith(prefix):
                tool_name = tool_name[len(prefix) :]
            span.set_attribute(GENAI_OPERATION_NAME, GENAI_OPERATION_MCP_REQUEST)
            span.set_attribute(GENAI_TOOL_NAME, tool_name)
            span.set_attribute("mcp.method", "tools/call")
            span.set_attribute("mcp.tool_name", name)
            input_data = arguments or {}
            outcome = "success"
            reason = ""
            error = ""

            try:
                if not is_allowed(tool_name):
                    outcome = "denied"
                    reason = "not in allow-list"
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"tool not allowed: {tool_name!r}")],
                        isError=True,
                    )

                tool = registry.get(tool_name)
                if tool is None:
                    outcome = "not_found"
                    error = f"tool not found: {tool_name!r}"
                    return CallToolResult(
                        content=[TextContent(type="text", text=error)],
                        isError=True,
                    )

                decision = await _authorize_tool_call(
                    tool_authorizer,
                    ToolAuthorizationRequest(tool_name=tool_name, mcp_name=name, arguments=input_data),
                )
                if decision.allowed and decider is not None:
                    authz_decision = await decider.decide(
                        DecisionRequest(
                            principal="mcp",
                            action="tool:invoke",
                            resource=tool_name,
                            scopes=tuple(tool.definition.envelope.scopes),
                            context={"mcp_name": name},
                        )
                    )
                    decision = ToolAuthorizationDecision(authz_decision.allowed, authz_decision.reason)
                reason = decision.reason
                if not decision.allowed:
                    outcome = "denied"
                    return CallToolResult(
                        content=[TextContent(type="text", text=_denied_message(decision.reason))],
                        isError=True,
                    )

                if max_input_bytes > 0 and _json_size_bytes(input_data) > max_input_bytes:
                    outcome = "input_too_large"
                    error = f"input size exceeds {max_input_bytes} bytes"
                    return CallToolResult(
                        content=[
                            TextContent(
                                type="text",
                                text=f"input too large: exceeds {max_input_bytes} bytes",
                            )
                        ],
                        isError=True,
                    )

                # Validate input.
                validation = tool.validate(input_data)
                if not validation.valid:
                    error_text = "; ".join(str(e) for e in validation.errors)
                    outcome = "validation_error"
                    error = error_text
                    return CallToolResult(
                        content=[TextContent(type="text", text=f"validation error: {error_text}")],
                        isError=True,
                    )

                ctx = Context()
                limit = max_result_bytes
                if limit > 0:
                    ctx.max_result_size = limit
                result = await registry.call(tool_name, ctx, input_data)
                if result.is_error:
                    outcome = "tool_error"
                    error = result.text()
                else:
                    if limit > 0 and _result_size_bytes(result) > limit:
                        outcome = "result_too_large"
                        error = f"result size exceeds {limit} bytes"
                        return CallToolResult(
                            content=[
                                TextContent(type="text", text=f"result too large: exceeds {limit} bytes")
                            ],
                            isError=True,
                        )
                    output_validation = _validate_tool_output(tool.definition, result)
                    if not output_validation.valid:
                        output_error = "; ".join(str(e.message) for e in output_validation.errors)
                        outcome = "output_validation_error"
                        error = output_error
                        return CallToolResult(
                            content=[
                                TextContent(
                                    type="text",
                                    text=f"output validation error: {output_error}",
                                )
                            ],
                            isError=True,
                        )
                return result_to_mcp_result(result)
            except Exception as exc:
                outcome = "tool_error"
                error = str(exc)
                raise
            finally:
                await _audit_tool_call(
                    tool_audit_sink,
                    ToolAuditEvent(
                        tool_name=tool_name,
                        mcp_name=name,
                        outcome=outcome,
                        reason=reason,
                        error=error,
                    ),
                )

    return server


async def _authorize_tool_call(
    authorizer: ToolAuthorizer | None,
    request: ToolAuthorizationRequest,
) -> ToolAuthorizationDecision:
    if authorizer is None:
        return ToolAuthorizationDecision(allowed=True, reason="no_authorizer")
    result = authorizer(request)
    if inspect.isawaitable(result):
        result = await result
    if isinstance(result, ToolAuthorizationDecision):
        return result
    return ToolAuthorizationDecision(allowed=bool(result))


async def _audit_tool_call(sink: ToolAuditSink | None, event: ToolAuditEvent) -> None:
    if sink is None:
        return
    result = sink(event)
    if inspect.isawaitable(result):
        await result


def _denied_message(reason: str) -> str:
    if not reason:
        return "tool call denied"
    return f"tool call denied: {reason}"


def _effective_result_limit(server_limit: int, tool_limit: int) -> int:
    if server_limit > 0 and tool_limit > 0:
        return min(server_limit, tool_limit)
    if server_limit > 0:
        return server_limit
    return tool_limit


def _json_size_bytes(value: object) -> int:
    return len(json.dumps(value, separators=(",", ":"), ensure_ascii=False).encode())


def _result_size_bytes(result: Result) -> int:
    if result.output is not None:
        return _json_size_bytes(result.output)
    return len(result.text().encode())


def _validate_tool_output(definition: Definition, result: Result) -> ValidationResult:
    if definition.output_schema is None or result.is_error:
        return ValidationResult(valid=True)
    candidate: object = result.output if result.output is not None else result.text()
    return validate(definition.output_schema, candidate)


async def _await_if_needed[T](value: T | Awaitable[T]) -> T:
    if inspect.isawaitable(value):
        return await value
    return value


def _resource_template_matches(template: str, uri: str) -> bool:
    literals = _template_literals(template)
    if not literals:
        return template == uri
    if not uri.startswith(literals[0]):
        return False
    index = len(literals[0])
    for literal in literals[1:]:
        if literal == "":
            continue
        next_index = uri.find(literal, index)
        if next_index == -1:
            return False
        index = next_index + len(literal)
    if template and not template.endswith("}") and literals[-1] != "":
        return uri.endswith(literals[-1])
    return True


def _template_literals(template: str) -> list[str]:
    literals: list[str] = []
    current: list[str] = []
    depth = 0
    for char in template:
        if char == "{":
            if depth == 0:
                literals.append("".join(current))
                current = []
            depth += 1
            continue
        if char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0:
                    continue
            current.append(char)
            continue
        if depth == 0:
            current.append(char)
    literals.append("".join(current))
    return literals

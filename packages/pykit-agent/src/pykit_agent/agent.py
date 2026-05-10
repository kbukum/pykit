"""Agent — bounded loop with canonical streaming events and observe-only hooks."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Protocol, cast, runtime_checkable

from opentelemetry import trace
from opentelemetry.trace import Tracer

from pykit_agent.hooks import (
    ErrorEvent,
    LLMRequestEvent,
    LLMResponseEvent,
    MCPRequestEvent,
    MCPResultEvent,
    StartEvent,
    StepCompleteEvent,
    StopEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from pykit_agent.types import (
    AgentEvent,
    AgentResult,
    ContextStrategy,
    HookError,
    MaxTokensExceededError,
    MaxToolCallsExceededError,
    MaxTurnsExceededError,
    StopReason,
    WallClockExceededError,
)
from pykit_ai import (
    Budget,
    Error,
    FinishReason,
    MessageStart,
    MessageStop,
    ToolResultBlock,
    Usage,
    UsageDelta,
)
from pykit_ai.semconv import (
    GENAI_OPERATION_AGENT_RUN,
    GENAI_OPERATION_AGENT_TURN,
    GENAI_OPERATION_NAME,
    GENAI_REQUEST_MODEL,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
)
from pykit_component import Health, HealthStatus
from pykit_hook import Action, Event
from pykit_hook import Registry as HookRegistry
from pykit_hook import Result as HookResult
from pykit_llm.provider import Provider, count_tokens_approx
from pykit_llm.types import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    Message,
    SystemMessage,
    tool_result_msg,
)
from pykit_resilience import Policy
from pykit_tool.context import Context
from pykit_tool.registry import BatchOptions, Registry
from pykit_tool.result import error_result as _tool_error

# Maps FinishReason values that have no matching StopReason string.
_FINISH_TO_STOP: dict[FinishReason, StopReason] = {
    FinishReason.TOOL_USE: StopReason.END_TURN,
    FinishReason.CONTENT_FILTER: StopReason.ERROR,
}


def _stop_reason(finish: FinishReason) -> StopReason:
    """Convert an LLM FinishReason to an agent StopReason without a mapper type."""
    return _FINISH_TO_STOP.get(finish) or StopReason(finish.value)


@dataclass
class AgentConfig:
    """Configuration for an Agent instance."""

    provider: Provider
    tools: Registry | None = None
    hooks: HookRegistry | None = None
    system_prompt: str = ""
    max_turns: int = 10
    max_tokens: int = 100_000
    wall_clock_seconds: float = 60.0
    max_tool_calls: int = 50
    budget: Budget = field(default_factory=lambda: Budget(max_tokens=100_000, max_calls=50, wall_clock=60.0))
    tool_concurrency: int = 4
    tool_timeout_seconds: float = 30.0
    context_strategy: ContextStrategy | None = None
    tracer: Tracer = field(default_factory=lambda: trace.get_tracer("pykit_agent"))
    policy: Policy | None = None

    def __post_init__(self) -> None:
        if self.tool_concurrency < 1:
            raise ValueError("tool_concurrency must be >= 1")


def _add_usage(total: Usage, delta: Usage) -> Usage:
    return Usage(
        input_tokens=total.input_tokens + delta.input_tokens,
        output_tokens=total.output_tokens + delta.output_tokens,
        cached_tokens=total.cached_tokens + delta.cached_tokens,
        reasoning_tokens=total.reasoning_tokens + delta.reasoning_tokens,
    )


@runtime_checkable
class _MCPBackedTool(Protocol):
    @property
    def mcp_server(self) -> str:
        """Return the MCP server name used by this tool."""

    @property
    def mcp_method(self) -> str:
        """Return the MCP method exposed by this tool."""


@dataclass
class _ResultHolder:
    """Per-call result holder; replaces shared instance state for concurrency safety."""

    value: AgentResult


class Agent:
    """Agentic loop: LLM → tool calls → LLM until done or limits reached."""

    def __init__(self, config: AgentConfig) -> None:
        self._config = config
        self._started = False
        self._last_run_at = 0.0

    @property
    def name(self) -> str:
        """Return the agent component name."""
        return "agent"

    async def start(self) -> None:
        """Mark the agent ready for execution."""
        self._started = True

    async def stop(self) -> None:
        """Mark the agent stopped."""
        self._started = False

    async def health(self) -> Health:
        """Return the current lifecycle health."""
        if not self._started:
            return Health(name=self.name, status=HealthStatus.UNHEALTHY, message="not started")
        message = "ready"
        if self._last_run_at > 0:
            message = f"last_run_at={self._last_run_at:.3f}"
        return Health(name=self.name, status=HealthStatus.HEALTHY, message=message)

    async def run(self, messages: list[Message]) -> AgentResult:
        """Run the agent loop to completion."""
        self._last_run_at = time.monotonic()
        with self._config.tracer.start_as_current_span("agent.run") as span:
            span.set_attribute(GENAI_OPERATION_NAME, GENAI_OPERATION_AGENT_RUN)
            async_messages = list(messages)
            holder = _ResultHolder(
                value=AgentResult(
                    async_messages, _last_assistant(async_messages), Usage(), 0, StopReason.ERROR
                )
            )
            async for event in self._stream(async_messages, holder):
                if isinstance(event, MessageStop):
                    response = cast("CompletionResponse | None", event.response)
                    if response is not None:
                        holder.value = AgentResult(
                            messages=[*async_messages, response.message],
                            final_message=response.message,
                            total_usage=response.usage,
                            turn_count=1,
                            stop_reason=_stop_reason(response.stop_reason),
                        )
            return holder.value

    async def stream(self, messages: list[Message]) -> AsyncIterator[AgentEvent]:
        """Run the bounded agent loop, yielding canonical LLM stream events."""
        self._last_run_at = time.monotonic()
        holder = _ResultHolder(
            value=AgentResult(list(messages), _last_assistant(messages), Usage(), 0, StopReason.ERROR)
        )
        async for event in self._stream(messages, holder):
            yield event

    async def _stream(self, messages: list[Message], holder: _ResultHolder) -> AsyncIterator[AgentEvent]:
        cfg = self._config
        msgs = list(messages)
        total_usage = Usage()
        tool_calls = 0
        started = time.monotonic()
        holder.value = AgentResult(msgs, _last_assistant(msgs), total_usage, 0, StopReason.ERROR)

        try:
            if cfg.max_turns <= 0:
                raise MaxTurnsExceededError("max turns exceeded")
            if cfg.max_tokens <= 0:
                raise MaxTokensExceededError("max token budget exceeded")
            if cfg.max_tool_calls < 0:
                raise MaxToolCallsExceededError("max tool-call budget exceeded")
            _check_wall_clock(started, cfg.wall_clock_seconds)

            for turn in range(1, cfg.max_turns + 1):
                _check_wall_clock(started, cfg.wall_clock_seconds)
                with cfg.tracer.start_as_current_span("agent.turn") as span:
                    span.set_attribute(GENAI_OPERATION_NAME, GENAI_OPERATION_AGENT_TURN)
                    await self._on_start(turn)
                    request = self._build_request(msgs)
                    span.set_attribute(GENAI_REQUEST_MODEL, request.model)
                    await self._on_llm_request(request)
                    start_event = MessageStart(model=request.model, role="assistant")
                    yield start_event

                    response = await self._invoke_provider(request, started)
                    await self._on_llm_response(response)
                    total_usage = _add_usage(total_usage, response.usage)
                    span.set_attribute(GENAI_USAGE_INPUT_TOKENS, total_usage.input_tokens)
                    span.set_attribute(GENAI_USAGE_OUTPUT_TOKENS, total_usage.output_tokens)
                    usage_event = UsageDelta(usage=response.usage, cached_tokens=None)
                    yield usage_event
                    if total_usage.input_tokens + total_usage.output_tokens >= cfg.max_tokens:
                        raise MaxTokensExceededError("max token budget exceeded")

                    msgs.append(response.message)
                    if not response.has_tool_calls():
                        complete = MessageStop(response=response)
                        await self._on_step_complete(turn, response.message)
                        stop = _stop_reason(response.stop_reason)
                        await self._on_stop(stop.value)
                        holder.value = AgentResult(msgs, response.message, total_usage, turn, stop)
                        yield complete
                        return

                    calls: list[tuple[str, dict[str, Any]]] = []
                    ids: list[str] = []
                    mcp_refs: list[tuple[str, str] | None] = []
                    for tc in response.message.tool_calls:
                        tool_calls += 1
                        if tool_calls > cfg.max_tool_calls:
                            raise MaxToolCallsExceededError("max tool-call budget exceeded")
                        tool_input = tc.input
                        await self._on_tool_call(tc.name, cast("dict[str, object]", tool_input))
                        mcp_ref = self._mcp_ref(tc.name)
                        if mcp_ref is not None:
                            await self._on_mcp_request(*mcp_ref, cast("dict[str, object]", tool_input))
                        calls.append((tc.name, tool_input))
                        ids.append(tc.id)
                        mcp_refs.append(mcp_ref)

                    if cfg.tools is None:
                        for tc in response.message.tool_calls:
                            block = _tool_error(f"no tool registry: cannot execute {tc.name}").to_block(tc.id)
                            await self._on_tool_result(tc.name, block)
                            raw = block.content[0] if block.content else ""
                            content = raw if isinstance(raw, str) else json.dumps(raw)
                            msgs.append(tool_result_msg(block.id, content, block.is_error))
                    else:
                        batch = cfg.tools.call_batch(
                            calls, Context(), BatchOptions(cfg.tool_concurrency, fail_fast=False)
                        )
                        results = await asyncio.wait_for(batch, timeout=cfg.tool_timeout_seconds)
                        for tool_id, (name, _input_data), mcp_ref, result in zip(
                            ids, calls, mcp_refs, results, strict=True
                        ):
                            block = result.to_block(tool_id)
                            await self._on_tool_result(name, block)
                            if mcp_ref is not None:
                                await self._on_mcp_result(*mcp_ref, block)
                            raw = block.content[0] if block.content else ""
                            content = raw if isinstance(raw, str) else json.dumps(raw)
                            msgs.append(tool_result_msg(block.id, content, block.is_error))

                    if cfg.context_strategy:
                        token_count = count_tokens_approx(msgs)
                        max_ctx = cfg.provider.capabilities().max_input_tokens
                        if max_ctx > 0 and token_count > max_ctx:
                            msgs = cfg.context_strategy.compact(msgs, max_ctx)
                    await self._on_step_complete(turn, response.message)

            raise MaxTurnsExceededError("max turns exceeded")
        except asyncio.CancelledError:
            event = MessageStop(finish_reason=FinishReason.CANCELLED)
            await self._on_stop(StopReason.CANCELLED.value)
            holder.value = AgentResult(msgs, _last_assistant(msgs), total_usage, 0, StopReason.CANCELLED)
            yield event
            raise
        except WallClockExceededError as exc:
            yield await self._terminal_error(exc, msgs, total_usage, StopReason.WALL_CLOCK, holder)
        except MaxTokensExceededError as exc:
            yield await self._terminal_error(exc, msgs, total_usage, StopReason.MAX_TOKENS, holder)
        except MaxToolCallsExceededError as exc:
            yield await self._terminal_error(exc, msgs, total_usage, StopReason.MAX_TOOL_CALLS, holder)
        except MaxTurnsExceededError as exc:
            yield await self._terminal_error(exc, msgs, total_usage, StopReason.MAX_TURNS, holder)
        except Exception as exc:
            await self._on_error(exc)
            await self._on_stop(StopReason.ERROR.value)
            raise

    async def _invoke_provider(self, request: CompletionRequest, started: float) -> CompletionResponse:
        cfg = self._config
        timeout = cfg.wall_clock_seconds - (time.monotonic() - started)

        async def _call() -> CompletionResponse:
            return await asyncio.wait_for(cfg.provider.complete(request), timeout=timeout)

        if cfg.policy is None:
            return await _call()
        return await cfg.policy.execute(_call)

    async def _terminal_error(
        self,
        exc: Exception,
        msgs: list[Message],
        usage: Usage,
        reason: StopReason,
        holder: _ResultHolder,
    ) -> Error:
        await self._on_error(exc)
        final_msg = _last_assistant(msgs)
        holder.value = AgentResult(msgs, final_msg, usage, len(msgs), reason)
        event = Error(error=str(exc), code=exc.__class__.__name__)
        await self._on_stop(reason.value)
        return event

    def _build_request(self, msgs: list[Message]) -> CompletionRequest:
        cfg = self._config
        request_msgs: list[Message] = list(msgs)
        if cfg.system_prompt:
            request_msgs = [SystemMessage(content=cfg.system_prompt), *request_msgs]
        tools = cfg.tools.list() if cfg.tools else None
        return CompletionRequest(messages=request_msgs, tools=tools if tools else None)

    def _mcp_ref(self, tool_name: str) -> tuple[str, str] | None:
        if self._config.tools is None:
            return None
        tool = self._config.tools.get(tool_name)
        if not isinstance(tool, _MCPBackedTool):
            return None
        return (tool.mcp_server, tool.mcp_method)

    async def _on_start(self, turn: int) -> None:
        await self._emit_hook(StartEvent(turn))

    async def _on_llm_request(self, request: CompletionRequest) -> None:
        await self._emit_hook(LLMRequestEvent(request))

    async def _on_llm_response(self, response: CompletionResponse) -> None:
        await self._emit_hook(LLMResponseEvent(response))

    async def _on_tool_call(self, name: str, input_data: dict[str, object]) -> None:
        await self._emit_hook(ToolCallEvent(name, input_data))

    async def _on_tool_result(self, name: str, result: ToolResultBlock) -> None:
        await self._emit_hook(ToolResultEvent(name, result))

    async def _on_mcp_request(self, server: str, method: str, input_data: dict[str, object]) -> None:
        await self._emit_hook(MCPRequestEvent(server, method, input_data))

    async def _on_mcp_result(self, server: str, method: str, result: object) -> None:
        await self._emit_hook(MCPResultEvent(server, method, result))

    async def _on_step_complete(self, turn: int, message: AssistantMessage) -> None:
        await self._emit_hook(StepCompleteEvent(turn, message))

    async def _on_error(self, error: Exception) -> None:
        await self._emit_hook(ErrorEvent(error))

    async def _on_stop(self, reason: str) -> None:
        await self._emit_hook(StopEvent(reason))

    async def _emit_hook(self, event: Event) -> None:
        hooks = self._config.hooks
        if hooks is None:
            return
        result = await hooks.emit_async(event)
        self._raise_for_hook_result(result)

    @staticmethod
    def _raise_for_hook_result(result: HookResult) -> None:
        if result.error is not None:
            raise HookError(str(result.error)) from result.error
        if result.action == Action.ABORT:
            raise HookError(result.reason or "hook execution aborted")


def _check_wall_clock(started: float, budget_seconds: float) -> None:
    if time.monotonic() - started >= budget_seconds:
        raise WallClockExceededError("wall-clock budget exceeded")


def _last_assistant(messages: list[Message]) -> AssistantMessage:
    for msg in reversed(messages):
        if isinstance(msg, AssistantMessage):
            return msg
    return AssistantMessage()

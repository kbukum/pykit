"""Agent — the core agent loop with tool execution and hooks."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, cast

from pykit_agent.hooks import (
    EVENT_ON_ERROR,
    EVENT_POST_LLM_CALL,
    EVENT_POST_TOOL_CALL,
    EVENT_PRE_LLM_CALL,
    EVENT_PRE_TOOL_CALL,
    EVENT_TURN_END,
    EVENT_TURN_START,
    OnError,
    PostLLMCall,
    PostToolCall,
    PreLLMCall,
    PreToolCall,
    TurnEnd,
    TurnStart,
)
from pykit_agent.types import (
    AgentEvent,
    AgentResult,
    CompleteEvent,
    ContextCompactedEvent,
    ContextStrategy,
    StopReason,
    ToolCompleteEvent,
    ToolExecutingEvent,
    TurnCompleteEvent,
    TurnStartEvent,
)
from pykit_hook.registry import HookRegistry
from pykit_hook.types import Action
from pykit_llm.provider import Provider, count_tokens_approx
from pykit_llm.types import (
    AssistantMessage,
    CompletionRequest,
    Message,
    SystemMessage,
    Usage,
    tool_result_msg,
)
from pykit_tool.context import Context
from pykit_tool.registry import Registry


@dataclass
class AgentConfig:
    """Configuration for an Agent instance."""

    provider: Provider
    tools: Registry | None = None
    hooks: HookRegistry | None = None
    system_prompt: str = ""
    max_turns: int = 100
    max_token_budget: int = 0
    context_strategy: ContextStrategy | None = None


def _add_usage(total: Usage, delta: Usage) -> Usage:
    """Accumulate token usage."""
    return Usage(
        prompt_tokens=total.prompt_tokens + delta.prompt_tokens,
        completion_tokens=total.completion_tokens + delta.completion_tokens,
        total_tokens=total.total_tokens + delta.total_tokens,
    )


class Agent:
    """Agentic loop: LLM → tool calls → LLM until done or limits reached."""

    def __init__(self, config: AgentConfig) -> None:
        self._config = config

    async def run(self, messages: list[Message]) -> AgentResult:
        """Run the agent loop to completion.

        Args:
            messages: Initial conversation messages.

        Returns:
            The final agent result.
        """
        result: AgentResult | None = None
        async for event in self.stream(messages):
            if isinstance(event, CompleteEvent):
                result = event.result
        assert result is not None, "stream must emit CompleteEvent"
        return result

    async def stream(self, messages: list[Message]) -> AsyncIterator[AgentEvent]:
        """Run the agent loop, yielding events as they occur.

        Args:
            messages: Initial conversation messages.

        Yields:
            Agent events for each step of the loop.
        """
        cfg = self._config
        msgs = list(messages)
        total_usage = Usage()

        for turn in range(1, cfg.max_turns + 1):
            yield TurnStartEvent(turn=turn)

            # Emit TurnStart hook
            if cfg.hooks and cfg.hooks.has_handlers(EVENT_TURN_START):
                hook_result = cfg.hooks.emit(TurnStart(type=EVENT_TURN_START, turn=turn))
                if hook_result.action == Action.ABORT:
                    result = AgentResult(
                        messages=msgs,
                        final_message=_last_assistant(msgs),
                        total_usage=total_usage,
                        turn_count=turn,
                        stop_reason=StopReason.ABORTED,
                    )
                    yield CompleteEvent(result=result)
                    return

            # Build request
            request = self._build_request(msgs)

            # Emit PreLLMCall hook (allow Modify to alter request)
            if cfg.hooks and cfg.hooks.has_handlers(EVENT_PRE_LLM_CALL):
                hook_result = cfg.hooks.emit(PreLLMCall(type=EVENT_PRE_LLM_CALL, request=request))
                if hook_result.action == Action.ABORT:
                    result = AgentResult(
                        messages=msgs,
                        final_message=_last_assistant(msgs),
                        total_usage=total_usage,
                        turn_count=turn,
                        stop_reason=StopReason.ABORTED,
                    )
                    yield CompleteEvent(result=result)
                    return
                if hook_result.action == Action.MODIFY and isinstance(
                    hook_result.modified_data, CompletionRequest
                ):
                    request = hook_result.modified_data

            # Call provider
            try:
                response = await cfg.provider.complete(request)
            except Exception as exc:
                if cfg.hooks and cfg.hooks.has_handlers(EVENT_ON_ERROR):
                    cfg.hooks.emit(OnError(type=EVENT_ON_ERROR, error=exc, source="llm"))
                raise

            total_usage = _add_usage(total_usage, response.usage)

            # Emit PostLLMCall hook
            if cfg.hooks and cfg.hooks.has_handlers(EVENT_POST_LLM_CALL):
                hook_result = cfg.hooks.emit(PostLLMCall(type=EVENT_POST_LLM_CALL, response=response))
                if hook_result.action == Action.ABORT:
                    result = AgentResult(
                        messages=msgs,
                        final_message=response.message,
                        total_usage=total_usage,
                        turn_count=turn,
                        stop_reason=StopReason.ABORTED,
                    )
                    yield CompleteEvent(result=result)
                    return

            # Append assistant message
            msgs.append(response.message)

            # If no tool calls, we're done
            if not response.has_tool_calls():
                yield TurnCompleteEvent(turn=turn, message=response.message, usage=response.usage)
                self._emit_turn_end(turn, response.message)
                result = AgentResult(
                    messages=msgs,
                    final_message=response.message,
                    total_usage=total_usage,
                    turn_count=turn,
                    stop_reason=StopReason.END_TURN,
                )
                yield CompleteEvent(result=result)
                return

            # Execute tool calls
            for tc in response.message.tool_calls:
                tool_input = _parse_arguments(tc.function.arguments)

                yield ToolExecutingEvent(
                    tool_use_id=tc.id,
                    name=tc.function.name,
                    input=tool_input,
                )

                # Emit PreToolCall hook
                if cfg.hooks and cfg.hooks.has_handlers(EVENT_PRE_TOOL_CALL):
                    hook_result = cfg.hooks.emit(
                        PreToolCall(
                            type=EVENT_PRE_TOOL_CALL,
                            name=tc.function.name,
                            input=tool_input,
                        )
                    )
                    if hook_result.action == Action.ABORT:
                        msgs.append(tool_result_msg(tc.id, f"aborted: {hook_result.reason}", is_error=True))
                        continue

                # Execute tool
                tool_result_content = ""
                tool_error: Exception | None = None
                if cfg.tools:
                    try:
                        ctx = Context(tool_use_id=tc.id)
                        result_obj = await cfg.tools.call(tc.function.name, ctx, tool_input)
                        tool_result_content = result_obj.text()
                    except Exception as exc:
                        tool_error = exc
                        tool_result_content = str(exc)
                        if cfg.hooks and cfg.hooks.has_handlers(EVENT_ON_ERROR):
                            cfg.hooks.emit(
                                OnError(type=EVENT_ON_ERROR, error=exc, source=f"tool:{tc.function.name}")
                            )
                else:
                    tool_result_content = f"no tool registry: cannot execute {tc.function.name}"

                # Emit PostToolCall hook
                if cfg.hooks and cfg.hooks.has_handlers(EVENT_POST_TOOL_CALL):
                    cfg.hooks.emit(
                        PostToolCall(
                            type=EVENT_POST_TOOL_CALL,
                            name=tc.function.name,
                            input=tool_input,
                            result=tool_result_content,
                            error=tool_error,
                        )
                    )

                yield ToolCompleteEvent(
                    tool_use_id=tc.id,
                    name=tc.function.name,
                    result=tool_result_content,
                    error=tool_error,
                )

                msgs.append(tool_result_msg(tc.id, tool_result_content, is_error=tool_error is not None))

            # Check token budget
            if cfg.max_token_budget > 0 and total_usage.total_tokens >= cfg.max_token_budget:
                yield TurnCompleteEvent(turn=turn, message=response.message, usage=response.usage)
                self._emit_turn_end(turn, response.message)
                result = AgentResult(
                    messages=msgs,
                    final_message=response.message,
                    total_usage=total_usage,
                    turn_count=turn,
                    stop_reason=StopReason.MAX_BUDGET,
                )
                yield CompleteEvent(result=result)
                return

            # Check context size and compact if needed
            if cfg.context_strategy:
                token_count = count_tokens_approx(msgs)
                max_ctx = cfg.provider.capabilities().max_context_tokens
                if max_ctx > 0 and token_count > max_ctx:
                    old_tokens = token_count
                    msgs = cfg.context_strategy.compact(msgs, max_ctx)
                    new_tokens = count_tokens_approx(msgs)
                    yield ContextCompactedEvent(old_tokens=old_tokens, new_tokens=new_tokens)

            yield TurnCompleteEvent(turn=turn, message=response.message, usage=response.usage)
            self._emit_turn_end(turn, response.message)

        # Max turns reached
        final_msg = _last_assistant(msgs)
        result = AgentResult(
            messages=msgs,
            final_message=final_msg,
            total_usage=total_usage,
            turn_count=cfg.max_turns,
            stop_reason=StopReason.MAX_TURNS,
        )
        yield CompleteEvent(result=result)

    def _build_request(self, msgs: list[Message]) -> CompletionRequest:
        """Build a CompletionRequest from messages and config."""
        cfg = self._config
        request_msgs: list[Message] = list(msgs)
        if cfg.system_prompt:
            request_msgs = [SystemMessage(content=cfg.system_prompt), *request_msgs]

        tools = cfg.tools.list() if cfg.tools else None

        return CompletionRequest(
            messages=request_msgs,
            tools=tools if tools else None,
        )

    def _emit_turn_end(self, turn: int, message: AssistantMessage) -> None:
        """Emit TurnEnd hook if handlers are registered."""
        cfg = self._config
        if cfg.hooks and cfg.hooks.has_handlers(EVENT_TURN_END):
            cfg.hooks.emit(TurnEnd(type=EVENT_TURN_END, turn=turn, message=message))


def _last_assistant(messages: list[Message]) -> AssistantMessage:
    """Find the last AssistantMessage, or return an empty one."""
    for msg in reversed(messages):
        if isinstance(msg, AssistantMessage):
            return msg
    return AssistantMessage()


def _parse_arguments(arguments: str) -> dict[str, Any]:
    """Parse JSON arguments string into a dict."""
    if not arguments:
        return {}
    try:
        return cast("dict[str, Any]", json.loads(arguments))
    except (json.JSONDecodeError, TypeError):
        return {"raw": arguments}

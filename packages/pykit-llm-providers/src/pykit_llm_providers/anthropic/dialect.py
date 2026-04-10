"""Anthropic Claude LLM provider backed by httpx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from pykit_llm.config import LLMConfig
from pykit_llm.errors import LLMError, LLMErrorCode
from pykit_llm.types import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    FunctionCall,
    Message,
    StreamChunk,
    SystemMessage,
    TextBlock,
    ToolCall,
    ToolResultBlock,
    ToolResultMessage,
    ToolUseBlock,
    Usage,
    UserMessage,
    text_of,
)
from pykit_llm_providers.anthropic.config import AnthropicConfig


class AnthropicProvider:
    """Anthropic Claude chat completion provider.

    Implements the :class:`~pykit_llm.provider.LLMProvider` protocol using
    the Anthropic Messages API (``/v1/messages``).
    """

    def __init__(
        self,
        config: AnthropicConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._llm_config = LLMConfig(
            base_url=config.base_url,
            api_key=config.api_key,
            model=config.model,
            timeout=config.timeout,
        )
        kwargs: dict[str, Any] = {
            "base_url": config.base_url,
            "timeout": config.timeout,
            "headers": {
                "x-api-key": config.api_key,
                "anthropic-version": config.api_version,
                "content-type": "application/json",
            },
        }
        if transport is not None:
            kwargs["transport"] = transport
        self._client = httpx.AsyncClient(**kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a messages request and return a single response."""
        payload = _build_payload(request, self._config)
        resp = await self._client.post("/v1/messages", json=payload)
        err = _classify_status(resp.status_code)
        if err is not None:
            raise err
        return _parse_response(resp.json())

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Stream messages via SSE."""
        payload = _build_payload(request, self._config)
        payload["stream"] = True
        try:
            async with self._client.stream("POST", "/v1/messages", json=payload) as resp:
                err = _classify_status(resp.status_code)
                if err is not None:
                    raise err
                async for chunk in _iter_sse(resp):
                    yield chunk
        except httpx.TimeoutException as exc:
            raise LLMError(str(exc), code=LLMErrorCode.TIMEOUT, retryable=True) from exc
        except httpx.ConnectError as exc:
            raise LLMError(str(exc), code=LLMErrorCode.CONNECTION, retryable=True) from exc

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------


def _build_payload(request: CompletionRequest, config: AnthropicConfig) -> dict[str, Any]:
    """Map a universal CompletionRequest to the Anthropic JSON body."""
    model = request.model or config.model
    max_tokens = request.max_tokens or config.max_tokens

    system_text = ""
    messages: list[dict[str, Any]] = []

    for msg in request.messages:
        match msg:
            case SystemMessage(content=content):
                system_text = content
            case _:
                messages.append(_encode_message(msg))

    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    if system_text:
        payload["system"] = system_text

    if request.temperature != 0.7:
        payload["temperature"] = request.temperature

    if request.stop:
        payload["stop_sequences"] = request.stop

    if request.extra:
        payload.update(request.extra)

    return payload


def _encode_message(msg: Message) -> dict[str, Any]:
    """Encode a discriminated union Message to the Anthropic wire format."""
    match msg:
        case UserMessage(content=blocks):
            content_parts: list[dict[str, Any]] = []
            for block in blocks:
                match block:
                    case ToolResultBlock(tool_use_id=tid, content=content, is_error=is_error):
                        part: dict[str, Any] = {
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "content": content,
                        }
                        if is_error:
                            part["is_error"] = True
                        content_parts.append(part)
                    case _:
                        content_parts.append({"type": "text", "text": text_of([block])})

            if len(content_parts) == 1 and content_parts[0].get("type") == "text":
                return {"role": "user", "content": content_parts[0]["text"]}
            return {"role": "user", "content": content_parts}

        case AssistantMessage(content=blocks):
            content_parts_a: list[dict[str, Any]] = []
            for block in blocks:
                match block:
                    case ToolUseBlock(id=tid, name=name, input=inp):
                        content_parts_a.append(
                            {
                                "type": "tool_use",
                                "id": tid,
                                "name": name,
                                "input": inp,
                            }
                        )
                    case _:
                        t = text_of([block])
                        if t:
                            content_parts_a.append({"type": "text", "text": t})

            if len(content_parts_a) == 1 and content_parts_a[0].get("type") == "text":
                return {"role": "assistant", "content": content_parts_a[0]["text"]}
            return {"role": "assistant", "content": content_parts_a}

        case ToolResultMessage(tool_use_id=tid, content=content, is_error=is_error):
            part_t: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": tid,
                "content": content,
            }
            if is_error:
                part_t["is_error"] = True
            return {"role": "user", "content": [part_t]}

        case _:
            return {"role": "user", "content": ""}


def _parse_response(data: dict[str, Any]) -> CompletionResponse:
    """Parse an Anthropic Messages API response."""
    content_blocks: list[TextBlock | ToolUseBlock] = []
    for block in data.get("content", []):
        if block["type"] == "text":
            content_blocks.append(TextBlock(text=block["text"]))
        elif block["type"] == "tool_use":
            content_blocks.append(
                ToolUseBlock(
                    id=block["id"],
                    name=block["name"],
                    input=block.get("input", {}),
                )
            )

    usage_data = data.get("usage", {})
    usage = Usage(
        prompt_tokens=usage_data.get("input_tokens", 0),
        completion_tokens=usage_data.get("output_tokens", 0),
        total_tokens=usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0),
    )

    stop_reason = data.get("stop_reason", "end_turn")

    message = AssistantMessage(content=content_blocks)

    return CompletionResponse(
        message=message,
        model=data.get("model", ""),
        usage=usage,
        stop_reason=stop_reason,
    )


def _classify_status(status_code: int) -> LLMError | None:
    """Map an HTTP status code to a typed LLM error."""
    if 200 <= status_code < 300:
        return None
    if status_code in (401, 403):
        return LLMError(
            f"HTTP {status_code}",
            status_code=status_code,
            code=LLMErrorCode.AUTH,
        )
    if status_code == 429:
        return LLMError(
            "HTTP 429",
            status_code=429,
            code=LLMErrorCode.RATE_LIMIT,
            retryable=True,
        )
    if 400 <= status_code < 500:
        return LLMError(
            f"HTTP {status_code}",
            status_code=status_code,
            code=LLMErrorCode.INVALID_REQUEST,
        )
    if status_code >= 500:
        return LLMError(
            f"HTTP {status_code}",
            status_code=status_code,
            code=LLMErrorCode.SERVER,
            retryable=True,
        )
    return LLMError(f"HTTP {status_code}", status_code=status_code, code=LLMErrorCode.SERVER)


async def _iter_sse(resp: httpx.Response) -> AsyncIterator[StreamChunk]:
    """Parse an SSE stream of Anthropic-style events."""
    async for line in resp.aiter_lines():
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        if line.startswith("event: "):
            continue
        if not line.startswith("data: "):
            continue
        payload = line[len("data: ") :]

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue

        event_type = data.get("type", "")

        if event_type == "content_block_start":
            cb = data.get("content_block", {})
            if cb.get("type") == "tool_use":
                yield StreamChunk(
                    tool_calls=[
                        ToolCall(
                            id=cb.get("id", ""),
                            function=FunctionCall(name=cb.get("name", ""), arguments=""),
                        )
                    ]
                )

        elif event_type == "content_block_delta":
            delta = data.get("delta", {})
            if delta.get("type") == "text_delta":
                yield StreamChunk(content=delta.get("text", ""))
            elif delta.get("type") == "input_json_delta":
                yield StreamChunk(
                    tool_calls=[
                        ToolCall(
                            id="",
                            function=FunctionCall(name="", arguments=delta.get("partial_json", "")),
                        )
                    ]
                )

        elif event_type == "message_delta":
            usage_data = data.get("usage", {})
            usage = (
                Usage(
                    prompt_tokens=usage_data.get("input_tokens", 0),
                    completion_tokens=usage_data.get("output_tokens", 0),
                    total_tokens=(usage_data.get("input_tokens", 0) + usage_data.get("output_tokens", 0)),
                )
                if usage_data
                else None
            )
            yield StreamChunk(usage=usage)

        elif event_type == "message_stop":
            yield StreamChunk(done=True)
            return

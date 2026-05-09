"""Anthropic Claude LLM provider backed by httpx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from pykit_ai import ContentBlock, FinishReason, TextBlock, ToolResultBlock, ToolUseBlock, Usage
from pykit_llm.config import LLMConfig
from pykit_llm.errors import LLMError, LLMErrorCode
from pykit_llm.provider import ProviderBase
from pykit_llm.types import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    Message,
    StreamChunk,
    SystemMessage,
    ToolResultMessage,
    UserMessage,
    _StreamToolCall,
    text_of,
)
from pykit_llm_providers.anthropic.config import AnthropicConfig

_ANTHROPIC_STOP_MAP: dict[str, FinishReason] = {
    "end_turn": FinishReason.STOP,
    "stop_sequence": FinishReason.STOP,
    "tool_use": FinishReason.TOOL_USE,
    "max_tokens": FinishReason.LENGTH,
}


class AnthropicProvider(ProviderBase):
    """Anthropic Claude chat completion provider."""

    _name = "anthropic"

    def __init__(
        self,
        config: AnthropicConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__()
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

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a messages request and return a single response."""
        self._touch()
        payload = _build_payload(request, self._config)
        resp = await self._client.post("/v1/messages", json=payload)
        err = _classify_status(resp.status_code)
        if err is not None:
            raise err
        return _parse_response(resp.json())

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Stream messages via SSE."""
        self._touch()
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


def _build_payload(request: CompletionRequest, config: AnthropicConfig) -> dict[str, Any]:
    """Map a universal CompletionRequest to the Anthropic JSON body."""
    model = request.model or config.model
    max_tokens = request.max_tokens or config.max_tokens
    system_text = ""
    messages: list[dict[str, Any]] = []
    for message in request.messages:
        match message:
            case SystemMessage(content=content):
                system_text = content
            case _:
                messages.append(_encode_message(message))
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
    """Encode a canonical Message to the Anthropic wire format."""
    match msg:
        case UserMessage(content=blocks):
            content_parts: list[dict[str, Any]] = []
            for block in blocks:
                match block:
                    case ToolResultBlock(id=tool_use_id, content=content, is_error=is_error):
                        part: dict[str, Any] = {
                            "type": "tool_result",
                            "tool_use_id": tool_use_id,
                            "content": content,
                        }
                        if is_error:
                            part["is_error"] = True
                        content_parts.append(part)
                    case _:
                        text = text_of([block])
                        if text:
                            content_parts.append({"type": "text", "text": text})
            if len(content_parts) == 1 and content_parts[0].get("type") == "text":
                return {"role": "user", "content": content_parts[0]["text"]}
            return {"role": "user", "content": content_parts}
        case AssistantMessage(content=blocks, tool_calls=tool_calls):
            asst_parts: list[dict[str, Any]] = []
            for block in blocks:
                text = text_of([block])
                if text:
                    asst_parts.append({"type": "text", "text": text})
            for tool_call in tool_calls:
                asst_parts.append(
                    {
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_call.name,
                        "input": tool_call.input,
                    }
                )
            if len(asst_parts) == 1 and asst_parts[0].get("type") == "text":
                return {"role": "assistant", "content": asst_parts[0]["text"]}
            return {"role": "assistant", "content": asst_parts}
        case ToolResultMessage(tool_use_id=tool_use_id, content=content, is_error=is_error):
            tool_msg_part: dict[str, Any] = {
                "type": "tool_result",
                "tool_use_id": tool_use_id,
                "content": content,
            }
            if is_error:
                tool_msg_part["is_error"] = True
            return {"role": "user", "content": [tool_msg_part]}
        case _:
            return {"role": "user", "content": ""}


def _parse_response(data: dict[str, Any]) -> CompletionResponse:
    """Parse an Anthropic Messages API response."""
    content_blocks: list[ContentBlock] = []
    tool_calls: list[ToolUseBlock] = []
    for block in data.get("content", []):
        if block["type"] == "text":
            content_blocks.append(TextBlock(text=block["text"]))
        elif block["type"] == "tool_use":
            tool_calls.append(
                ToolUseBlock(
                    id=block.get("id", ""),
                    name=block.get("name", ""),
                    input=block.get("input", {}),
                )
            )
    usage_data = data.get("usage", {})
    usage = Usage(
        input_tokens=usage_data.get("input_tokens", 0),
        output_tokens=usage_data.get("output_tokens", 0),
    )
    stop_reason = _ANTHROPIC_STOP_MAP.get(data.get("stop_reason", "end_turn"), FinishReason.STOP)
    message = AssistantMessage(content=content_blocks, tool_calls=tool_calls, usage=usage)
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
        return LLMError(f"HTTP {status_code}", status_code=status_code, code=LLMErrorCode.AUTH)
    if status_code == 429:
        return LLMError("HTTP 429", status_code=429, code=LLMErrorCode.RATE_LIMIT, retryable=True)
    if 400 <= status_code < 500:
        return LLMError(f"HTTP {status_code}", status_code=status_code, code=LLMErrorCode.INVALID_REQUEST)
    if status_code >= 500:
        return LLMError(
            f"HTTP {status_code}", status_code=status_code, code=LLMErrorCode.SERVER, retryable=True
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
            block = data.get("content_block", {})
            if block.get("type") == "tool_use":
                yield StreamChunk(
                    tool_calls=[
                        _StreamToolCall(
                            index=data.get("index", 0),
                            id=block.get("id", ""),
                            name=block.get("name", ""),
                            input_delta="",
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
                        _StreamToolCall(
                            index=data.get("index", 0),
                            input_delta=delta.get("partial_json", ""),
                        )
                    ]
                )
        elif event_type == "message_delta":
            usage_data = data.get("usage", {})
            usage = (
                Usage(
                    input_tokens=usage_data.get("input_tokens", 0),
                    output_tokens=usage_data.get("output_tokens", 0),
                )
                if usage_data
                else None
            )
            yield StreamChunk(usage=usage)
        elif event_type == "message_stop":
            yield StreamChunk(done=True)
            return

"""OpenAI-compatible LLM provider backed by httpx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from pykit_ai import FinishReason, TextBlock, ToolUseBlock, Usage
from pykit_llm.config import LLMConfig
from pykit_llm.errors import LLMError, LLMErrorCode, classify_status
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
from pykit_llm_openai.config import OpenAIConfig

_OPENAI_STOP_MAP: dict[str, FinishReason] = {
    "stop": FinishReason.STOP,
    "tool_calls": FinishReason.TOOL_USE,
    "length": FinishReason.LENGTH,
    "content_filter": FinishReason.CONTENT_FILTER,
}

_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider(ProviderBase):
    """OpenAI-compatible chat completion provider."""

    _name = "openai"

    def __init__(
        self,
        config: LLMConfig | OpenAIConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__()
        if isinstance(config, OpenAIConfig):
            self._config = LLMConfig(
                base_url=config.base_url,
                api_key=config.api_key,
                model=config.model,
                timeout=config.timeout,
            )
        else:
            self._config = config

        base_url = self._config.base_url or _DEFAULT_BASE_URL
        kwargs: dict[str, Any] = {
            "base_url": base_url,
            "timeout": self._config.timeout,
            "headers": {
                "authorization": f"Bearer {self._config.api_key}",
                "content-type": "application/json",
            },
        }
        if transport is not None:
            kwargs["transport"] = transport
        self._client = httpx.AsyncClient(**kwargs)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a chat completion request and return a single response."""
        self._touch()
        payload = _build_payload(request, self._config, stream=False)
        resp = await self._client.post("/chat/completions", json=payload)
        err = classify_status(resp.status_code)
        if err is not None:
            raise err
        return _parse_response(resp.json())

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Stream chat completion chunks via SSE."""
        self._touch()
        payload = _build_payload(request, self._config, stream=True)
        try:
            async with self._client.stream("POST", "/chat/completions", json=payload) as resp:
                err = classify_status(resp.status_code)
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


def _build_payload(request: CompletionRequest, config: LLMConfig, *, stream: bool) -> dict[str, Any]:
    """Map a universal CompletionRequest to the OpenAI JSON body."""
    model = request.model or config.model
    payload: dict[str, Any] = {
        "model": model,
        "messages": [_encode_message(message) for message in request.messages],
        "temperature": request.temperature,
        "stream": stream,
    }
    if request.max_tokens is not None:
        payload["max_tokens"] = request.max_tokens
    if request.stop:
        payload["stop"] = request.stop
    if request.extra:
        payload.update(request.extra)
    return payload


def _encode_message(msg: Message) -> dict[str, Any]:
    """Encode a canonical Message to the OpenAI wire format."""
    match msg:
        case UserMessage(content=blocks):
            return {"role": "user", "content": text_of(blocks)}
        case AssistantMessage(content=blocks, tool_calls=tool_calls):
            encoded: dict[str, Any] = {"role": "assistant", "content": text_of(blocks)}
            if tool_calls:
                encoded["tool_calls"] = [
                    {
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.name,
                            "arguments": json.dumps(tool_call.input),
                        },
                    }
                    for tool_call in tool_calls
                ]
            return encoded
        case SystemMessage(content=content):
            return {"role": "system", "content": content}
        case ToolResultMessage(tool_use_id=tool_use_id, content=content):
            return {"role": "tool", "content": content, "tool_call_id": tool_use_id}
        case _:
            raise ValueError(f"Unsupported OpenAI message type: {type(msg).__name__}")


def _parse_response(data: dict[str, Any]) -> CompletionResponse:
    choice = data["choices"][0]
    message_data = choice.get("message", {})
    usage_data = data.get("usage")
    usage = (
        Usage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
        )
        if usage_data
        else Usage()
    )
    content = message_data.get("content") or ""
    tool_calls: list[ToolUseBlock] = []
    for tool_call in message_data.get("tool_calls", []):
        raw_args = tool_call.get("function", {}).get("arguments", "{}")
        try:
            input_map = json.loads(raw_args) if raw_args else {}
        except json.JSONDecodeError:
            input_map = {"raw": raw_args}
        if not isinstance(input_map, dict):
            input_map = {"value": input_map}
        tool_calls.append(
            ToolUseBlock(
                id=tool_call.get("id", ""),
                name=tool_call.get("function", {}).get("name", ""),
                input=input_map,
            )
        )
    message = AssistantMessage(
        content=[TextBlock(text=content)] if content else [],
        tool_calls=tool_calls,
        usage=usage,
    )
    return CompletionResponse(
        message=message,
        model=data.get("model", ""),
        usage=usage,
        stop_reason=_OPENAI_STOP_MAP.get(choice.get("finish_reason", "stop"), FinishReason.STOP),
    )


async def _iter_sse(resp: httpx.Response) -> AsyncIterator[StreamChunk]:
    """Parse an SSE stream of OpenAI-style chunks."""
    async for line in resp.aiter_lines():
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        if not line.startswith("data: "):
            continue
        payload = line[len("data: ") :]
        if payload == "[DONE]":
            yield StreamChunk(done=True)
            return
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        delta = data.get("choices", [{}])[0].get("delta", {})
        content = delta.get("content", "")
        stream_tool_calls: list[_StreamToolCall] | None = None
        tool_calls_data = delta.get("tool_calls")
        if tool_calls_data:
            stream_tool_calls = []
            for tool_call in tool_calls_data:
                function = tool_call.get("function", {})
                stream_tool_calls.append(
                    _StreamToolCall(
                        index=tool_call.get("index", 0),
                        id=tool_call.get("id", ""),
                        name=function.get("name", ""),
                        input_delta=function.get("arguments", ""),
                    )
                )
        usage_data = data.get("usage")
        usage = (
            Usage(
                input_tokens=usage_data.get("prompt_tokens", 0),
                output_tokens=usage_data.get("completion_tokens", 0),
            )
            if usage_data
            else None
        )
        yield StreamChunk(content=content, usage=usage, tool_calls=stream_tool_calls)

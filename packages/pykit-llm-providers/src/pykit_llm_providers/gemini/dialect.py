"""Google Gemini LLM provider backed by httpx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from pykit_ai import ContentBlock, FinishReason, TextBlock, ToolUseBlock, Usage
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
from pykit_llm_providers.gemini.config import GeminiConfig

_STOP_REASON_MAP: dict[str, FinishReason] = {
    "STOP": FinishReason.STOP,
    "MAX_TOKENS": FinishReason.LENGTH,
    "SAFETY": FinishReason.CONTENT_FILTER,
    "RECITATION": FinishReason.CONTENT_FILTER,
    "TOOL_USE": FinishReason.TOOL_USE,
}


class GeminiProvider(ProviderBase):
    """Google Gemini chat completion provider."""

    _name = "gemini"

    def __init__(
        self,
        config: GeminiConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        super().__init__()
        self._config = config
        headers: dict[str, str] = {"content-type": "application/json"}
        if config.api_key:
            headers["x-goog-api-key"] = config.api_key
        kwargs: dict[str, Any] = {
            "base_url": config.base_url,
            "timeout": config.timeout,
            "headers": headers,
        }
        if transport is not None:
            kwargs["transport"] = transport
        self._client = httpx.AsyncClient(**kwargs)

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a generateContent request and return a single response."""
        self._touch()
        model = request.model or self._config.model
        payload = _build_payload(request, self._config)
        path = f"/v1beta/models/{model}:generateContent"
        resp = await self._client.post(path, json=payload)
        err = _classify_status(resp.status_code)
        if err is not None:
            raise err
        return _parse_response(resp.json())

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Stream generateContent via SSE."""
        self._touch()
        model = request.model or self._config.model
        payload = _build_payload(request, self._config)
        path = f"/v1beta/models/{model}:streamGenerateContent"
        try:
            async with self._client.stream(
                "POST",
                path,
                json=payload,
                params={"alt": "sse"},
            ) as resp:
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


def _build_payload(request: CompletionRequest, config: GeminiConfig) -> dict[str, Any]:
    """Map a universal CompletionRequest to the Gemini JSON body."""
    system_text = ""
    contents: list[dict[str, Any]] = []
    for message in request.messages:
        match message:
            case SystemMessage(content=content):
                system_text = content
            case _:
                contents.append(_encode_message(message))
    payload: dict[str, Any] = {"contents": contents}
    if system_text:
        payload["systemInstruction"] = {"parts": [{"text": system_text}]}
    generation_config: dict[str, Any] = {
        "temperature": request.temperature,
        "maxOutputTokens": request.max_tokens or config.max_output_tokens,
    }
    if request.stop:
        generation_config["stopSequences"] = request.stop
    payload["generationConfig"] = generation_config
    if request.tools:
        payload["tools"] = [
            {
                "functionDeclarations": [
                    {
                        "name": tool.name,
                        "description": tool.description,
                        **({"parameters": tool.input_schema} if tool.input_schema else {}),
                    }
                    for tool in request.tools
                ]
            }
        ]
    if request.extra:
        payload.update(request.extra)
    return payload


def _encode_message(msg: Message) -> dict[str, Any]:
    """Encode a canonical Message to the Gemini wire format."""
    match msg:
        case UserMessage(content=blocks):
            return {"role": "user", "parts": [{"text": text_of([block])} for block in blocks]}
        case AssistantMessage(content=blocks, tool_calls=tool_calls):
            parts: list[dict[str, Any]] = []
            for block in blocks:
                text = text_of([block])
                if text:
                    parts.append({"text": text})
            for tool_call in tool_calls:
                parts.append({"functionCall": {"name": tool_call.name, "args": tool_call.input}})
            return {"role": "model", "parts": parts}
        case ToolResultMessage(tool_use_id=tool_use_id, content=content):
            return {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": tool_use_id,
                            "response": {"result": content},
                        }
                    }
                ],
            }
        case _:
            raise ValueError(f"Unsupported Gemini message type: {type(msg).__name__}")


def _parse_response(data: dict[str, Any]) -> CompletionResponse:
    """Parse a Gemini generateContent response."""
    candidates = data.get("candidates", [])
    if not candidates:
        return CompletionResponse(message=AssistantMessage(content=[]), model="", usage=Usage())
    candidate = candidates[0]
    parts = candidate.get("content", {}).get("parts", [])
    content_blocks: list[ContentBlock] = []
    tool_calls: list[ToolUseBlock] = []
    for part in parts:
        if "text" in part:
            content_blocks.append(TextBlock(text=part["text"]))
        elif "functionCall" in part:
            function_call = part["functionCall"]
            tool_calls.append(
                ToolUseBlock(
                    id=function_call.get("name", ""),
                    name=function_call.get("name", ""),
                    input=function_call.get("args", {}),
                )
            )
    usage_meta = data.get("usageMetadata", {})
    usage = Usage(
        input_tokens=usage_meta.get("promptTokenCount", 0),
        output_tokens=usage_meta.get("candidatesTokenCount", 0),
    )
    stop_reason = _STOP_REASON_MAP.get(candidate.get("finishReason", "STOP"), FinishReason.STOP)
    message = AssistantMessage(content=content_blocks, tool_calls=tool_calls, usage=usage)
    return CompletionResponse(
        message=message,
        model=data.get("modelVersion", ""),
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
    """Parse an SSE stream of Gemini-style events."""
    async for line in resp.aiter_lines():
        line = line.strip()
        if not line or line.startswith(":"):
            continue
        if not line.startswith("data: "):
            continue
        payload = line[len("data: ") :]
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue
        candidates = data.get("candidates", [])
        if not candidates:
            continue
        candidate = candidates[0]
        parts = candidate.get("content", {}).get("parts", [])
        text_content = ""
        tool_calls: list[_StreamToolCall] = []
        for part in parts:
            if "text" in part:
                text_content += part["text"]
            elif "functionCall" in part:
                function_call = part["functionCall"]
                tool_calls.append(
                    _StreamToolCall(
                        id=function_call.get("name", ""),
                        name=function_call.get("name", ""),
                        input_delta=json.dumps(function_call.get("args", {})),
                    )
                )
        usage_meta = data.get("usageMetadata")
        usage = (
            Usage(
                input_tokens=usage_meta.get("promptTokenCount", 0),
                output_tokens=usage_meta.get("candidatesTokenCount", 0),
            )
            if usage_meta
            else None
        )
        finish_reason = candidate.get("finishReason")
        done = bool(finish_reason)
        yield StreamChunk(content=text_content, usage=usage, done=done, tool_calls=tool_calls or None)

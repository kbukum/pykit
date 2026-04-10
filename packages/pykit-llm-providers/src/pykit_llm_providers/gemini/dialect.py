"""Google Gemini LLM provider backed by httpx.

The Gemini API uses a structurally different format from OpenAI/Anthropic:
- Endpoint: /v1beta/models/{model}:generateContent
- Content uses "parts" (text, functionCall, functionResponse)
- System prompt → systemInstruction
- Config → generationConfig (temperature, maxOutputTokens, topP, stopSequences)
- Tools → functionDeclarations
- API key auth via query parameter ?key=API_KEY
- Response: candidates[].content.parts[], usageMetadata
- Stop reasons: STOP, MAX_TOKENS, SAFETY, TOOL_USE
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

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
    ToolResultMessage,
    ToolUseBlock,
    Usage,
    UserMessage,
    text_of,
)
from pykit_llm_providers.gemini.config import GeminiConfig

_STOP_REASON_MAP: dict[str, str] = {
    "STOP": "end_turn",
    "MAX_TOKENS": "max_tokens",
    "SAFETY": "content_filter",
    "RECITATION": "content_filter",
    "TOOL_USE": "tool_use",
}


class GeminiProvider:
    """Google Gemini chat completion provider.

    Implements the :class:`~pykit_llm.provider.LLMProvider` protocol using
    the Generative Language API.
    """

    def __init__(
        self,
        config: GeminiConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        kwargs: dict[str, Any] = {
            "base_url": config.base_url,
            "timeout": config.timeout,
            "headers": {"content-type": "application/json"},
        }
        if transport is not None:
            kwargs["transport"] = transport
        self._client = httpx.AsyncClient(**kwargs)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a generateContent request and return a single response."""
        model = request.model or self._config.model
        payload = _build_payload(request, self._config)
        path = f"/v1beta/models/{model}:generateContent"
        resp = await self._client.post(
            path,
            json=payload,
            params={"key": self._config.api_key},
        )
        err = _classify_status(resp.status_code)
        if err is not None:
            raise err
        return _parse_response(resp.json())

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Stream generateContent via SSE."""
        model = request.model or self._config.model
        payload = _build_payload(request, self._config)
        path = f"/v1beta/models/{model}:streamGenerateContent"
        try:
            async with self._client.stream(
                "POST",
                path,
                json=payload,
                params={"key": self._config.api_key, "alt": "sse"},
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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------


def _build_payload(request: CompletionRequest, config: GeminiConfig) -> dict[str, Any]:
    """Map a universal CompletionRequest to the Gemini JSON body."""
    system_text = ""
    contents: list[dict[str, Any]] = []

    for msg in request.messages:
        match msg:
            case SystemMessage(content=content):
                system_text = content
            case _:
                contents.append(_encode_message(msg))

    payload: dict[str, Any] = {"contents": contents}

    if system_text:
        payload["systemInstruction"] = {
            "parts": [{"text": system_text}],
        }

    gen_config: dict[str, Any] = {}
    gen_config["temperature"] = request.temperature
    max_tokens = request.max_tokens or config.max_output_tokens
    gen_config["maxOutputTokens"] = max_tokens
    if request.stop:
        gen_config["stopSequences"] = request.stop
    payload["generationConfig"] = gen_config

    if request.tools:
        func_declarations = []
        for tool in request.tools:
            decl: dict[str, Any] = {"name": tool.name, "description": tool.description}
            if tool.parameters:
                decl["parameters"] = tool.parameters
            func_declarations.append(decl)
        payload["tools"] = [{"functionDeclarations": func_declarations}]

    if request.extra:
        payload.update(request.extra)

    return payload


def _encode_message(msg: Message) -> dict[str, Any]:
    """Encode a discriminated union Message to the Gemini wire format."""
    match msg:
        case UserMessage(content=blocks):
            parts: list[dict[str, Any]] = []
            for block in blocks:
                parts.append({"text": text_of([block])})
            return {"role": "user", "parts": parts}

        case AssistantMessage(content=blocks):
            parts_a: list[dict[str, Any]] = []
            for block in blocks:
                match block:
                    case ToolUseBlock(name=name, input=inp):
                        parts_a.append({"functionCall": {"name": name, "args": inp}})
                    case _:
                        t = text_of([block])
                        if t:
                            parts_a.append({"text": t})
            return {"role": "model", "parts": parts_a}

        case ToolResultMessage(tool_use_id=_tid, content=content):
            return {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "name": _tid,
                            "response": {"result": content},
                        }
                    }
                ],
            }

        case _:
            return {"role": "user", "parts": [{"text": ""}]}


def _parse_response(data: dict[str, Any]) -> CompletionResponse:
    """Parse a Gemini generateContent response."""
    candidates = data.get("candidates", [])
    if not candidates:
        return CompletionResponse(
            message=AssistantMessage(content=[]),
            model="",
            usage=Usage(),
            stop_reason="",
        )

    candidate = candidates[0]
    content_data = candidate.get("content", {})
    parts = content_data.get("parts", [])

    content_blocks: list[TextBlock | ToolUseBlock] = []
    for part in parts:
        if "text" in part:
            content_blocks.append(TextBlock(text=part["text"]))
        elif "functionCall" in part:
            fc = part["functionCall"]
            content_blocks.append(
                ToolUseBlock(
                    id=fc.get("name", ""),
                    name=fc.get("name", ""),
                    input=fc.get("args", {}),
                )
            )

    usage_meta = data.get("usageMetadata", {})
    usage = Usage(
        prompt_tokens=usage_meta.get("promptTokenCount", 0),
        completion_tokens=usage_meta.get("candidatesTokenCount", 0),
        total_tokens=usage_meta.get("totalTokenCount", 0),
    )

    finish_reason = candidate.get("finishReason", "STOP")
    stop_reason = _STOP_REASON_MAP.get(finish_reason, finish_reason)

    message = AssistantMessage(content=content_blocks)

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
        content_data = candidate.get("content", {})
        parts = content_data.get("parts", [])

        text_content = ""
        tool_calls: list[ToolCall] = []
        for part in parts:
            if "text" in part:
                text_content += part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    ToolCall(
                        id=fc.get("name", ""),
                        function=FunctionCall(
                            name=fc.get("name", ""),
                            arguments=json.dumps(fc.get("args", {})),
                        ),
                    )
                )

        usage_meta = data.get("usageMetadata")
        usage = (
            Usage(
                prompt_tokens=usage_meta.get("promptTokenCount", 0),
                completion_tokens=usage_meta.get("candidatesTokenCount", 0),
                total_tokens=usage_meta.get("totalTokenCount", 0),
            )
            if usage_meta
            else None
        )

        finish_reason = candidate.get("finishReason")
        done = finish_reason is not None and finish_reason != ""

        yield StreamChunk(
            content=text_content,
            usage=usage,
            done=done,
            tool_calls=tool_calls or None,
        )

"""OpenAI-compatible LLM provider backed by httpx."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from pykit_llm.config import LLMConfig
from pykit_llm.errors import LLMError, LLMErrorCode, classify_status
from pykit_llm.types import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    Message,
    StreamChunk,
    SystemMessage,
    TextBlock,
    ToolResultMessage,
    Usage,
    UserMessage,
    text_of,
)
from pykit_llm_providers.openai.config import OpenAIConfig

_DEFAULT_BASE_URL = "https://api.openai.com/v1"


class OpenAIProvider:
    """OpenAI-compatible chat completion provider."""

    def __init__(
        self,
        config: LLMConfig | OpenAIConfig,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
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

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a chat completion request and return a single response."""
        payload = _build_payload(request, self._config, stream=False)
        resp = await self._client.post("/chat/completions", json=payload)
        err = classify_status(resp.status_code)
        if err is not None:
            raise err
        return _parse_response(resp.json())

    async def stream(self, request: CompletionRequest) -> AsyncIterator[StreamChunk]:
        """Stream chat completion chunks via SSE."""
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

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------


def _build_payload(request: CompletionRequest, config: LLMConfig, *, stream: bool) -> dict[str, Any]:
    """Map a universal CompletionRequest to the OpenAI JSON body."""
    model = request.model or config.model
    payload: dict[str, Any] = {
        "model": model,
        "messages": [_encode_message(m) for m in request.messages],
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


def _encode_message(msg: Message) -> dict[str, str]:
    """Encode a discriminated union Message to the OpenAI wire format."""
    match msg:
        case UserMessage(content=blocks):
            return {"role": "user", "content": text_of(blocks)}
        case AssistantMessage(content=blocks):
            return {"role": "assistant", "content": text_of(blocks)}
        case SystemMessage(content=content):
            return {"role": "system", "content": content}
        case ToolResultMessage(tool_use_id=tid, content=content):
            return {"role": "tool", "content": content, "tool_call_id": tid}
        case _:
            return {"role": "user", "content": ""}


def _parse_response(data: dict[str, Any]) -> CompletionResponse:
    choice = data["choices"][0]
    usage_data = data.get("usage")
    usage = (
        Usage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            completion_tokens=usage_data.get("completion_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )
        if usage_data
        else Usage()
    )
    content = choice["message"]["content"]
    message = AssistantMessage(content=[TextBlock(text=content)])

    return CompletionResponse(
        message=message,
        model=data.get("model", ""),
        usage=usage,
        stop_reason=choice.get("finish_reason", "stop"),
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

        usage_data = data.get("usage")
        usage = (
            Usage(
                prompt_tokens=usage_data.get("prompt_tokens", 0),
                completion_tokens=usage_data.get("completion_tokens", 0),
                total_tokens=usage_data.get("total_tokens", 0),
            )
            if usage_data
            else None
        )
        yield StreamChunk(content=content, usage=usage)

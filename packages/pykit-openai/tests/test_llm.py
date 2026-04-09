"""Tests for OpenAI LLM provider."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_llm import (
    CompletionRequest,
    LLMConfig,
    LLMProvider,
    StreamChunk,
    user,
)
from pykit_llm.errors import LLMError, LLMErrorCode
from pykit_openai import OpenAIConfig, OpenAIProvider


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _openai_response(
    content: str = "Hello!",
    model: str = "gpt-4",
    finish_reason: str = "stop",
) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }


def _sse_lines(*chunks: str, done: bool = True) -> str:
    lines: list[str] = []
    for i, c in enumerate(chunks):
        data = {
            "id": f"chatcmpl-{i}",
            "object": "chat.completion.chunk",
            "model": "gpt-4",
            "choices": [{"index": 0, "delta": {"content": c}, "finish_reason": None}],
        }
        lines.append(f"data: {json.dumps(data)}\n\n")
    if done:
        lines.append("data: [DONE]\n\n")
    return "".join(lines)


class TestOpenAIProviderProtocol:
    def test_implements_llm_provider(self):
        cfg = LLMConfig(api_key="test")
        provider = OpenAIProvider(cfg)
        assert isinstance(provider, LLMProvider)

    def test_accepts_openai_config(self):
        cfg = OpenAIConfig(api_key="test", model="gpt-4o")
        provider = OpenAIProvider(cfg)
        assert isinstance(provider, LLMProvider)


class TestOpenAIComplete:
    @pytest.fixture
    def config(self):
        return LLMConfig(api_key="sk-test", model="gpt-4")

    async def test_complete_success(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == "gpt-4"
            assert body["messages"][0]["role"] == "user"
            assert body["stream"] is False
            return httpx.Response(200, json=_openai_response())

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[user("Hi")])
            resp = await provider.complete(req)
            assert resp.text() == "Hello!"
            assert resp.model == "gpt-4"
            assert resp.usage.prompt_tokens == 10
            assert resp.stop_reason == "stop"
        finally:
            await provider.close()

    async def test_complete_sends_auth_header(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == "Bearer sk-test"
            return httpx.Response(200, json=_openai_response())

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            await provider.complete(CompletionRequest(messages=[user("Hi")]))
        finally:
            await provider.close()

    async def test_complete_401(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "Unauthorized"}})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert exc_info.value.code == LLMErrorCode.AUTH
        finally:
            await provider.close()

    async def test_complete_429(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": {"message": "Rate limited"}})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert exc_info.value.code == LLMErrorCode.RATE_LIMIT
            assert exc_info.value.retryable is True
        finally:
            await provider.close()


class TestOpenAIStream:
    @pytest.fixture
    def config(self):
        return LLMConfig(api_key="sk-test", model="gpt-4")

    async def test_stream_chunks(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["stream"] is True
            sse = _sse_lines("Hello", " world", "!")
            return httpx.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            chunks: list[StreamChunk] = []
            async for chunk in provider.stream(CompletionRequest(messages=[user("Hi")])):
                chunks.append(chunk)
            assert len(chunks) == 4
            assert chunks[0].content == "Hello"
            assert chunks[3].done is True
        finally:
            await provider.close()

    async def test_stream_timeout(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("read timed out")

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                async for _ in provider.stream(CompletionRequest(messages=[user("Hi")])):
                    pass
            assert exc_info.value.code == LLMErrorCode.TIMEOUT
            assert exc_info.value.retryable is True
        finally:
            await provider.close()


class TestOpenAIWithUnifiedConfig:
    async def test_complete_with_openai_config(self):
        cfg = OpenAIConfig(api_key="sk-unified", model="gpt-4o")

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == "Bearer sk-unified"
            body = json.loads(request.content)
            assert body["model"] == "gpt-4o"
            return httpx.Response(200, json=_openai_response(model="gpt-4o"))

        provider = OpenAIProvider(cfg, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert resp.model == "gpt-4o"
        finally:
            await provider.close()

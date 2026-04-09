"""Tests for Anthropic LLM provider."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_llm import (
    CompletionRequest,
    LLMProvider,
    StreamChunk,
    system,
    user,
)
from pykit_llm.errors import LLMError, LLMErrorCode
from pykit_llm_providers.anthropic import AnthropicConfig, AnthropicProvider


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _anthropic_response(
    content: str = "Hello!",
    model: str = "claude-sonnet-4-20250514",
    stop_reason: str = "end_turn",
) -> dict:
    return {
        "id": "msg-test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": content}],
        "stop_reason": stop_reason,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def _sse_stream(*chunks: str, done: bool = True) -> str:
    """Build Anthropic-style SSE events from content chunks."""
    lines: list[str] = []

    start = {
        "type": "message_start",
        "message": {
            "id": "msg-test",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-20250514",
            "usage": {"input_tokens": 10, "output_tokens": 0},
        },
    }
    lines.append(f"event: message_start\ndata: {json.dumps(start)}\n\n")

    block_start = {"type": "content_block_start", "index": 0, "content_block": {"type": "text", "text": ""}}
    lines.append(f"event: content_block_start\ndata: {json.dumps(block_start)}\n\n")

    for c in chunks:
        delta = {
            "type": "content_block_delta",
            "index": 0,
            "delta": {"type": "text_delta", "text": c},
        }
        lines.append(f"event: content_block_delta\ndata: {json.dumps(delta)}\n\n")

    block_stop = {"type": "content_block_stop", "index": 0}
    lines.append(f"event: content_block_stop\ndata: {json.dumps(block_stop)}\n\n")

    if done:
        msg_delta = {
            "type": "message_delta",
            "delta": {"stop_reason": "end_turn"},
            "usage": {"output_tokens": 5},
        }
        lines.append(f"event: message_delta\ndata: {json.dumps(msg_delta)}\n\n")

        msg_stop = {"type": "message_stop"}
        lines.append(f"event: message_stop\ndata: {json.dumps(msg_stop)}\n\n")

    return "".join(lines)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestAnthropicConfig:
    def test_defaults(self):
        cfg = AnthropicConfig()
        assert cfg.base_url == "https://api.anthropic.com"
        assert cfg.api_key == ""
        assert cfg.model == "claude-sonnet-4-20250514"
        assert cfg.api_version == "2023-06-01"
        assert cfg.timeout == 120.0
        assert cfg.max_tokens == 4096

    def test_custom(self):
        cfg = AnthropicConfig(
            api_key="sk-ant-test",
            model="claude-opus-4-20250514",
            max_tokens=8192,
        )
        assert cfg.api_key == "sk-ant-test"
        assert cfg.model == "claude-opus-4-20250514"
        assert cfg.max_tokens == 8192


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class TestAnthropicProviderProtocol:
    def test_implements_llm_provider(self):
        cfg = AnthropicConfig(api_key="test")
        provider = AnthropicProvider(cfg)
        assert isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# Complete
# ---------------------------------------------------------------------------


class TestAnthropicComplete:
    @pytest.fixture
    def config(self):
        return AnthropicConfig(api_key="sk-ant-test", model="claude-sonnet-4-20250514")

    async def test_complete_success(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == "claude-sonnet-4-20250514"
            assert body["max_tokens"] == 4096
            assert body["messages"][0]["role"] == "user"
            return httpx.Response(200, json=_anthropic_response())

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert resp.text() == "Hello!"
            assert resp.model == "claude-sonnet-4-20250514"
            assert resp.usage.prompt_tokens == 10
            assert resp.usage.completion_tokens == 5
            assert resp.usage.total_tokens == 15
            assert resp.stop_reason == "end_turn"
        finally:
            await provider.close()

    async def test_complete_with_system_message(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["system"] == "You are helpful"
            for msg in body["messages"]:
                assert msg["role"] != "system"
            return httpx.Response(200, json=_anthropic_response())

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(
                CompletionRequest(messages=[system("You are helpful"), user("Hi")])
            )
            assert resp.text() == "Hello!"
        finally:
            await provider.close()

    async def test_complete_sends_anthropic_headers(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["x-api-key"] == "sk-ant-test"
            assert request.headers["anthropic-version"] == "2023-06-01"
            return httpx.Response(200, json=_anthropic_response())

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            await provider.complete(CompletionRequest(messages=[user("Hi")]))
        finally:
            await provider.close()

    async def test_complete_401(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert exc_info.value.code == LLMErrorCode.AUTH
        finally:
            await provider.close()

    async def test_complete_429(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": {"message": "Rate limited"}})

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert exc_info.value.code == LLMErrorCode.RATE_LIMIT
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_complete_500(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": {"message": "Internal error"}})

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert exc_info.value.code == LLMErrorCode.SERVER
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_complete_custom_max_tokens(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["max_tokens"] == 1024
            return httpx.Response(200, json=_anthropic_response())

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(CompletionRequest(messages=[user("Hi")], max_tokens=1024))
            assert resp.text() == "Hello!"
        finally:
            await provider.close()


# ---------------------------------------------------------------------------
# Stream
# ---------------------------------------------------------------------------


class TestAnthropicStream:
    @pytest.fixture
    def config(self):
        return AnthropicConfig(api_key="sk-ant-test", model="claude-sonnet-4-20250514")

    async def test_stream_chunks(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["stream"] is True
            sse = _sse_stream("Hello", " world", "!")
            return httpx.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            chunks: list[StreamChunk] = []
            async for chunk in provider.stream(CompletionRequest(messages=[user("Hi")])):
                chunks.append(chunk)
            content_chunks = [c for c in chunks if c.content]
            done_chunks = [c for c in chunks if c.done]
            assert len(content_chunks) == 3
            assert content_chunks[0].content == "Hello"
            assert content_chunks[1].content == " world"
            assert content_chunks[2].content == "!"
            assert len(done_chunks) == 1
        finally:
            await provider.close()

    async def test_stream_timeout(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("read timed out")

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                async for _ in provider.stream(CompletionRequest(messages=[user("Hi")])):
                    pass
            assert exc_info.value.code == LLMErrorCode.TIMEOUT
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_stream_connect_error(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                async for _ in provider.stream(CompletionRequest(messages=[user("Hi")])):
                    pass
            assert exc_info.value.code == LLMErrorCode.CONNECTION
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_stream_401(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "Unauthorized"}})

        provider = AnthropicProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                async for _ in provider.stream(CompletionRequest(messages=[user("Hi")])):
                    pass
            assert exc_info.value.code == LLMErrorCode.AUTH
        finally:
            await provider.close()

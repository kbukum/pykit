"""Tests for Gemini LLM provider."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_ai import FinishReason, ToolUseBlock
from pykit_llm import (
    CompletionRequest,
    LLMProvider,
    StreamChunk,
    system,
    user,
)
from pykit_llm.errors import LLMError, LLMErrorCode
from pykit_llm_providers.gemini import GeminiConfig, GeminiProvider


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _assemble_tool_calls(chunks: list[StreamChunk]) -> list[ToolUseBlock]:
    states: dict[int, dict[str, str]] = {}
    for chunk in chunks:
        for tool_call in chunk.tool_calls or []:
            state = states.setdefault(tool_call.index, {"id": "", "name": "", "input_json": ""})
            if tool_call.id:
                state["id"] = tool_call.id
            if tool_call.name:
                state["name"] = tool_call.name
            state["input_json"] += tool_call.input_delta

    tool_calls: list[ToolUseBlock] = []
    for index in sorted(states):
        state = states[index]
        input_data = json.loads(state["input_json"] or "{}")
        assert isinstance(input_data, dict)
        tool_calls.append(ToolUseBlock(id=state["id"], name=state["name"], input=input_data))
    return tool_calls


def _gemini_response(
    content: str = "Hello!",
    model_version: str = "gemini-2.0-flash",
    finish_reason: str = "STOP",
) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [{"text": content}],
                    "role": "model",
                },
                "finishReason": finish_reason,
            }
        ],
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 5,
            "totalTokenCount": 15,
        },
        "modelVersion": model_version,
    }


def _sse_stream(*chunks: str, done: bool = True) -> str:
    """Build Gemini-style SSE events from content chunks."""
    lines: list[str] = []
    for i, c in enumerate(chunks):
        is_last = done and i == len(chunks) - 1
        data: dict = {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": c}],
                        "role": "model",
                    },
                }
            ],
        }
        if is_last:
            data["candidates"][0]["finishReason"] = "STOP"
            data["usageMetadata"] = {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            }
        lines.append(f"data: {json.dumps(data)}\n\n")
    return "".join(lines)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestGeminiConfig:
    def test_defaults(self):
        cfg = GeminiConfig()
        assert cfg.base_url == "https://generativelanguage.googleapis.com"
        assert cfg.api_key == ""
        assert cfg.model == "gemini-2.0-flash"
        assert cfg.timeout == 120.0
        assert cfg.max_output_tokens == 4096

    def test_custom(self):
        cfg = GeminiConfig(
            api_key="test-key",
            model="gemini-1.5-pro",
            max_output_tokens=8192,
        )
        assert cfg.api_key == "test-key"
        assert cfg.model == "gemini-1.5-pro"
        assert cfg.max_output_tokens == 8192


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


class TestGeminiProviderProtocol:
    def test_implements_llm_provider(self):
        cfg = GeminiConfig(api_key="test")
        provider = GeminiProvider(cfg)
        assert isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# Complete
# ---------------------------------------------------------------------------


class TestGeminiComplete:
    @pytest.fixture
    def config(self):
        return GeminiConfig(api_key="test-key", model="gemini-2.0-flash")

    async def test_complete_success(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers.get("x-goog-api-key") == "test-key"
            assert "key=" not in str(request.url)
            assert "/v1beta/models/gemini-2.0-flash:generateContent" in str(request.url)
            body = json.loads(request.content)
            assert body["contents"][0]["role"] == "user"
            assert body["contents"][0]["parts"][0]["text"] == "Hi"
            return httpx.Response(200, json=_gemini_response())

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert resp.text() == "Hello!"
            assert resp.usage.input_tokens == 10
            assert resp.usage.output_tokens == 5
            assert resp.usage.input_tokens + resp.usage.output_tokens == 15
            assert resp.stop_reason == FinishReason.STOP
        finally:
            await provider.close()

    async def test_complete_with_system_message(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["systemInstruction"]["parts"][0]["text"] == "You are helpful"
            # System message should NOT be in contents
            for c in body["contents"]:
                assert c["role"] != "system"
            return httpx.Response(200, json=_gemini_response())

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(
                CompletionRequest(messages=[system("You are helpful"), user("Hi")])
            )
            assert resp.text() == "Hello!"
        finally:
            await provider.close()

    async def test_complete_sends_api_key_as_header(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers.get("x-goog-api-key") == "test-key"
            assert "key=" not in str(request.url)
            assert "authorization" not in request.headers
            return httpx.Response(200, json=_gemini_response())

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            await provider.complete(CompletionRequest(messages=[user("Hi")]))
        finally:
            await provider.close()

    async def test_complete_generation_config(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            gen_config = body["generationConfig"]
            assert gen_config["temperature"] == 0.2
            assert gen_config["maxOutputTokens"] == 100
            assert gen_config["stopSequences"] == ["\n"]
            return httpx.Response(200, json=_gemini_response())

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(
                CompletionRequest(
                    messages=[user("Hi")],
                    temperature=0.2,
                    max_tokens=100,
                    stop=["\n"],
                )
            )
            assert resp.text() == "Hello!"
        finally:
            await provider.close()

    async def test_complete_401(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "Invalid API key"}})

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert exc_info.value.code == LLMErrorCode.AUTH
        finally:
            await provider.close()

    async def test_complete_429(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": {"message": "Rate limited"}})

        provider = GeminiProvider(config, transport=_mock_transport(handler))
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

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert exc_info.value.code == LLMErrorCode.SERVER
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_complete_empty_candidates(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"candidates": []})

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert resp.text() == ""
        finally:
            await provider.close()

    async def test_complete_max_tokens_stop_reason(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_gemini_response(finish_reason="MAX_TOKENS"))

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert resp.stop_reason == FinishReason.LENGTH
        finally:
            await provider.close()

    async def test_complete_safety_stop_reason(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_gemini_response(finish_reason="SAFETY"))

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(CompletionRequest(messages=[user("Hi")]))
            assert resp.stop_reason == FinishReason.CONTENT_FILTER
        finally:
            await provider.close()


# ---------------------------------------------------------------------------
# Stream
# ---------------------------------------------------------------------------


class TestGeminiStream:
    @pytest.fixture
    def config(self):
        return GeminiConfig(api_key="test-key", model="gemini-2.0-flash")

    async def test_stream_chunks(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            assert "alt=sse" in str(request.url)
            assert ":streamGenerateContent" in str(request.url)
            sse = _sse_stream("Hello", " world", "!")
            return httpx.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})

        provider = GeminiProvider(config, transport=_mock_transport(handler))
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

        provider = GeminiProvider(config, transport=_mock_transport(handler))
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

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            with pytest.raises(LLMError) as exc_info:
                async for _ in provider.stream(CompletionRequest(messages=[user("Hi")])):
                    pass
            assert exc_info.value.code == LLMErrorCode.CONNECTION
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_stream_function_call(self, config):
        """functionCall parts in the SSE stream assemble into canonical tool blocks."""
        data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "get_weather",
                                    "args": {"location": "NYC"},
                                }
                            }
                        ],
                        "role": "model",
                    },
                    "finishReason": "TOOL_USE",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
        }
        sse = f"data: {json.dumps(data)}\n\n"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            chunks = [chunk async for chunk in provider.stream(CompletionRequest(messages=[user("weather")]))]
            assert _assemble_tool_calls(chunks) == [
                ToolUseBlock(id="get_weather", name="get_weather", input={"location": "NYC"})
            ]
            assert sum(chunk.done for chunk in chunks) == 1
        finally:
            await provider.close()

    async def test_stream_with_usage(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            sse = _sse_stream("Hello")
            return httpx.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            chunks: list[StreamChunk] = []
            async for chunk in provider.stream(CompletionRequest(messages=[user("Hi")])):
                chunks.append(chunk)
            done_chunks = [c for c in chunks if c.done]
            assert len(done_chunks) == 1
            assert done_chunks[0].usage is not None
            assert done_chunks[0].usage.input_tokens + done_chunks[0].usage.output_tokens == 15
        finally:
            await provider.close()


class TestGeminiResponseToolCalls:
    @pytest.fixture
    def config(self):
        return GeminiConfig(api_key="test-key", model="gemini-2.0-flash")

    async def test_complete_parses_function_call_as_tool_use_block(self, config):
        data = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "get_weather",
                                    "args": {"location": "NYC"},
                                }
                            }
                        ],
                        "role": "model",
                    },
                    "finishReason": "TOOL_USE",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 10,
                "candidatesTokenCount": 5,
                "totalTokenCount": 15,
            },
            "modelVersion": "gemini-2.0-flash",
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=data)

        provider = GeminiProvider(config, transport=_mock_transport(handler))
        try:
            resp = await provider.complete(CompletionRequest(messages=[user("weather")]))
            assert len(resp.message.tool_calls) == 1
            tool_call = resp.message.tool_calls[0]
            assert tool_call.id == "get_weather"
            assert tool_call.name == "get_weather"
            assert tool_call.input == {"location": "NYC"}
        finally:
            await provider.close()

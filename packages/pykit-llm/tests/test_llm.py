"""Comprehensive tests for pykit_llm."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_llm import (
    AssistantMessage,
    CompletionRequest,
    CompletionResponse,
    LLMConfig,
    LLMProvider,
    StopReason,
    StreamChunk,
    TextBlock,
    Usage,
    assistant,
    system,
    text_of,
    user,
)
from pykit_llm.errors import (
    LLMError,
    LLMErrorCode,
    classify_status,
)
from pykit_openai import OpenAIProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_transport(handler):
    """Create an httpx.MockTransport from an async handler."""
    return httpx.MockTransport(handler)


def _openai_response(content: str = "Hello!", model: str = "gpt-4", finish_reason: str = "stop") -> dict:
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
    """Build an SSE payload from content chunks."""
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


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------


class TestTypes:
    def test_user_message(self):
        m = user("hi")
        assert m.role == "user"
        assert text_of(m.content) == "hi"

    def test_assistant_message(self):
        m = assistant("hello")
        assert m.role == "assistant"
        assert text_of(m.content) == "hello"

    def test_system_message(self):
        m = system("you are helpful")
        assert m.role == "system"
        assert m.content == "you are helpful"

    def test_tool_result_message(self):
        from pykit_llm import tool_result_msg

        m = tool_result_msg("tu-1", "result data")
        assert m.role == "tool_result"
        assert m.tool_use_id == "tu-1"
        assert m.content == "result data"
        assert m.is_error is False

    def test_text_of(self):
        blocks = [TextBlock(text="hello"), TextBlock(text=" world")]
        assert text_of(blocks) == "hello world"

    def test_stop_reason_constants(self):
        assert StopReason.END_TURN == "end_turn"
        assert StopReason.TOOL_USE == "tool_use"
        assert StopReason.MAX_TOKENS == "max_tokens"

    def test_usage_defaults(self):
        u = Usage()
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0

    def test_completion_request_defaults(self):
        req = CompletionRequest(messages=[])
        assert req.model == ""
        assert req.temperature == 0.7
        assert req.max_tokens is None
        assert req.stream is False
        assert req.stop is None
        assert req.extra == {}

    def test_completion_response(self):
        msg = AssistantMessage(content=[TextBlock(text="hello")])
        r = CompletionResponse(message=msg, model="gpt-4")
        assert r.text() == "hello"
        assert r.stop_reason == ""
        assert r.usage.prompt_tokens == 0

    def test_completion_response_has_tool_calls(self):
        msg = AssistantMessage()
        r = CompletionResponse(message=msg)
        assert r.has_tool_calls() is False

    def test_stream_chunk_defaults(self):
        c = StreamChunk()
        assert c.content == ""
        assert c.done is False
        assert c.usage is None


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class TestConfig:
    def test_llm_config_defaults(self):
        cfg = LLMConfig()
        assert cfg.provider == "openai"
        assert cfg.base_url == ""
        assert cfg.api_key == ""
        assert cfg.model == ""
        assert cfg.timeout == 120.0
        assert cfg.max_retries == 3

    def test_llm_config_custom(self):
        cfg = LLMConfig(
            provider="azure",
            base_url="https://my.endpoint.com",
            api_key="sk-test",
            model="gpt-4o",
            timeout=30.0,
            max_retries=1,
        )
        assert cfg.provider == "azure"
        assert cfg.api_key == "sk-test"
        assert cfg.model == "gpt-4o"
        assert cfg.timeout == 30.0


# ---------------------------------------------------------------------------
# Provider protocol conformance
# ---------------------------------------------------------------------------


class TestProviderProtocol:
    def test_openai_provider_is_llm_provider(self):
        cfg = LLMConfig(api_key="test")
        provider = OpenAIProvider(cfg)
        assert isinstance(provider, LLMProvider)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class TestErrors:
    def test_classify_2xx(self):
        assert classify_status(200) is None
        assert classify_status(201) is None

    def test_classify_401(self):
        err = classify_status(401)
        assert err is not None
        assert err.code == LLMErrorCode.AUTH
        assert err.status_code == 401

    def test_classify_429(self):
        err = classify_status(429)
        assert err is not None
        assert err.code == LLMErrorCode.RATE_LIMIT
        assert err.retryable is True

    def test_classify_500(self):
        err = classify_status(500)
        assert err is not None
        assert err.code == LLMErrorCode.SERVER
        assert err.retryable is True

    def test_classify_400(self):
        err = classify_status(400)
        assert err is not None
        assert err.code == LLMErrorCode.INVALID_REQUEST

    def test_error_str_with_status(self):
        err = LLMError("oops", status_code=500, code=LLMErrorCode.SERVER)
        assert "HTTP 500" in str(err)

    def test_error_str_without_status(self):
        err = LLMError("stream broke", code=LLMErrorCode.STREAM)
        assert "stream" in str(err).lower()


# ---------------------------------------------------------------------------
# OpenAI provider — complete
# ---------------------------------------------------------------------------


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
            assert resp.usage.completion_tokens == 5
            assert resp.usage.total_tokens == 15
            assert resp.stop_reason == "stop"
        finally:
            await provider.close()

    async def test_complete_with_options(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["temperature"] == 0.2
            assert body["max_tokens"] == 100
            assert body["stop"] == ["\n"]
            return httpx.Response(200, json=_openai_response())

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(
                messages=[user("Hi")],
                temperature=0.2,
                max_tokens=100,
                stop=["\n"],
            )
            resp = await provider.complete(req)
            assert resp.text() == "Hello!"
        finally:
            await provider.close()

    async def test_complete_request_model_overrides_config(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["model"] == "gpt-3.5-turbo"
            return httpx.Response(200, json=_openai_response(model="gpt-3.5-turbo"))

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(
                messages=[user("Hi")],
                model="gpt-3.5-turbo",
            )
            resp = await provider.complete(req)
            assert resp.model == "gpt-3.5-turbo"
        finally:
            await provider.close()

    async def test_complete_sends_auth_header(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == "Bearer sk-test"
            return httpx.Response(200, json=_openai_response())

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[user("Hi")])
            await provider.complete(req)
        finally:
            await provider.close()

    async def test_complete_system_message(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["messages"][0]["role"] == "system"
            assert body["messages"][0]["content"] == "You are helpful"
            return httpx.Response(200, json=_openai_response())

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[system("You are helpful")])
            await provider.complete(req)
        finally:
            await provider.close()


# ---------------------------------------------------------------------------
# OpenAI provider — stream
# ---------------------------------------------------------------------------


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
            req = CompletionRequest(messages=[user("Hi")])
            chunks: list[StreamChunk] = []
            async for chunk in provider.stream(req):
                chunks.append(chunk)
            assert len(chunks) == 4  # 3 content + 1 done
            assert chunks[0].content == "Hello"
            assert chunks[1].content == " world"
            assert chunks[2].content == "!"
            assert chunks[3].done is True
        finally:
            await provider.close()

    async def test_stream_empty(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            sse = "data: [DONE]\n\n"
            return httpx.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[user("Hi")])
            chunks = [c async for c in provider.stream(req)]
            assert len(chunks) == 1
            assert chunks[0].done is True
        finally:
            await provider.close()


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    @pytest.fixture
    def config(self):
        return LLMConfig(api_key="bad-key", model="gpt-4")

    async def test_complete_401(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "Unauthorized"}})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[user("Hi")])
            with pytest.raises(LLMError) as exc_info:
                await provider.complete(req)
            assert exc_info.value.code == LLMErrorCode.AUTH
            assert exc_info.value.status_code == 401
        finally:
            await provider.close()

    async def test_complete_429(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, json={"error": {"message": "Rate limited"}})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[user("Hi")])
            with pytest.raises(LLMError) as exc_info:
                await provider.complete(req)
            assert exc_info.value.code == LLMErrorCode.RATE_LIMIT
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_complete_500(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"error": {"message": "Internal"}})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[user("Hi")])
            with pytest.raises(LLMError) as exc_info:
                await provider.complete(req)
            assert exc_info.value.code == LLMErrorCode.SERVER
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_stream_401(self, config):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": {"message": "Unauthorized"}})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[user("Hi")])
            with pytest.raises(LLMError) as exc_info:
                async for _ in provider.stream(req):
                    pass
            assert exc_info.value.code == LLMErrorCode.AUTH
        finally:
            await provider.close()

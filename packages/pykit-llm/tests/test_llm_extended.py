"""Extended tests for pykit_llm — edge cases, error paths, and coverage gaps."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_llm import (
    CompletionRequest,
    CompletionResponse,
    LLMConfig,
    LLMProvider,
    Message,
    Role,
    StreamChunk,
    Usage,
)
from pykit_llm.errors import (
    LLMError,
    LLMErrorCode,
    auth_error,
    classify_status,
    rate_limit_error,
    server_error,
    stream_error,
)
from pykit_llm.openai import OpenAIProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_transport(handler):
    return httpx.MockTransport(handler)


def _openai_response(
    content: str = "Hello!",
    model: str = "gpt-4",
    finish_reason: str = "stop",
    usage: dict | None = None,
) -> dict:
    return {
        "id": "chatcmpl-ext-test",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ],
        "usage": usage or {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
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


# ---------------------------------------------------------------------------
# Error classification edge cases
# ---------------------------------------------------------------------------


class TestErrorClassificationExtended:
    def test_classify_403_is_auth(self):
        err = classify_status(403)
        assert err is not None
        assert err.code == LLMErrorCode.AUTH
        assert err.status_code == 403

    def test_classify_502_is_server(self):
        err = classify_status(502)
        assert err is not None
        assert err.code == LLMErrorCode.SERVER
        assert err.retryable is True

    def test_classify_503_is_server(self):
        err = classify_status(503)
        assert err is not None
        assert err.code == LLMErrorCode.SERVER

    def test_classify_422_is_invalid_request(self):
        err = classify_status(422)
        assert err is not None
        assert err.code == LLMErrorCode.INVALID_REQUEST

    def test_classify_204_is_none(self):
        assert classify_status(204) is None

    def test_factory_auth_error(self):
        err = auth_error(401)
        assert err.code == LLMErrorCode.AUTH
        assert err.status_code == 401
        assert err.retryable is False

    def test_factory_rate_limit_error(self):
        err = rate_limit_error()
        assert err.code == LLMErrorCode.RATE_LIMIT
        assert err.retryable is True
        assert err.status_code == 429

    def test_factory_server_error(self):
        err = server_error(503)
        assert err.code == LLMErrorCode.SERVER
        assert err.retryable is True
        assert err.status_code == 503

    def test_factory_stream_error(self):
        err = stream_error("connection dropped")
        assert err.code == LLMErrorCode.STREAM
        assert "connection dropped" in str(err)
        assert err.retryable is False


# ---------------------------------------------------------------------------
# LLMError formatting
# ---------------------------------------------------------------------------


class TestLLMErrorFormatting:
    def test_all_error_codes_in_str(self):
        for code in LLMErrorCode:
            err = LLMError(f"test-{code}", code=code)
            s = str(err)
            assert code in s, f"code {code!r} missing from {s!r}"

    def test_retryable_flag_preserved(self):
        err = LLMError("retry me", code=LLMErrorCode.RATE_LIMIT, retryable=True)
        assert err.retryable is True
        err2 = LLMError("no retry", code=LLMErrorCode.AUTH, retryable=False)
        assert err2.retryable is False

    def test_llm_error_is_exception(self):
        err = LLMError("boom", code=LLMErrorCode.SERVER)
        assert isinstance(err, Exception)


# ---------------------------------------------------------------------------
# Role enum edge cases
# ---------------------------------------------------------------------------


class TestRoleExtended:
    def test_role_is_str(self):
        """Role values can be compared as plain strings."""
        assert Role.SYSTEM == "system"
        assert str(Role.TOOL) == "tool"

    def test_role_membership(self):
        assert "user" in [r.value for r in Role]
        assert "admin" not in [r.value for r in Role]

    def test_role_iteration(self):
        roles = list(Role)
        assert len(roles) == 4


# ---------------------------------------------------------------------------
# Usage edge cases
# ---------------------------------------------------------------------------


class TestUsageExtended:
    def test_usage_with_zeros(self):
        u = Usage(prompt_tokens=0, completion_tokens=0, total_tokens=0)
        assert u.prompt_tokens == 0
        assert u.completion_tokens == 0
        assert u.total_tokens == 0

    def test_usage_large_values(self):
        u = Usage(prompt_tokens=1_000_000, completion_tokens=500_000, total_tokens=1_500_000)
        assert u.prompt_tokens + u.completion_tokens == u.total_tokens


# ---------------------------------------------------------------------------
# CompletionRequest validation edge cases
# ---------------------------------------------------------------------------


class TestCompletionRequestExtended:
    def test_empty_messages_list(self):
        req = CompletionRequest(messages=[])
        assert req.messages == []

    def test_negative_temperature(self):
        """Negative temperature is structurally allowed (validation is provider's job)."""
        req = CompletionRequest(messages=[], temperature=-0.5)
        assert req.temperature == -0.5

    def test_zero_temperature(self):
        req = CompletionRequest(messages=[], temperature=0.0)
        assert req.temperature == 0.0

    def test_extra_dict_passthrough(self):
        req = CompletionRequest(
            messages=[Message(role=Role.USER, content="hi")],
            extra={"top_p": 0.9, "presence_penalty": 0.5},
        )
        assert req.extra["top_p"] == 0.9
        assert req.extra["presence_penalty"] == 0.5

    def test_stop_sequences(self):
        req = CompletionRequest(messages=[], stop=["###", "\n\n"])
        assert req.stop == ["###", "\n\n"]


# ---------------------------------------------------------------------------
# StreamChunk edge cases
# ---------------------------------------------------------------------------


class TestStreamChunkExtended:
    def test_done_with_content(self):
        c = StreamChunk(content="final word", done=True)
        assert c.content == "final word"
        assert c.done is True

    def test_done_with_usage(self):
        u = Usage(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        c = StreamChunk(done=True, usage=u)
        assert c.usage is not None
        assert c.usage.total_tokens == 15


# ---------------------------------------------------------------------------
# Config edge cases
# ---------------------------------------------------------------------------


class TestConfigExtended:
    def test_config_missing_fields(self):
        """Config with all defaults — no required fields."""
        cfg = LLMConfig()
        assert cfg.api_key == ""
        assert cfg.model == ""
        assert cfg.base_url == ""

    def test_config_zero_timeout(self):
        cfg = LLMConfig(timeout=0.0)
        assert cfg.timeout == 0.0

    def test_config_negative_retries(self):
        """Negative retries is structurally allowed."""
        cfg = LLMConfig(max_retries=-1)
        assert cfg.max_retries == -1


# ---------------------------------------------------------------------------
# OpenAI provider — stream timeout & connection errors
# ---------------------------------------------------------------------------


class TestOpenAIStreamErrorsExtended:
    @pytest.fixture()
    def config(self):
        return LLMConfig(api_key="sk-test", model="gpt-4")

    async def test_stream_timeout(self, config):
        """Timeout during streaming raises LLMError with TIMEOUT code."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("read timed out")

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[Message(role=Role.USER, content="Hi")])
            with pytest.raises(LLMError) as exc_info:
                async for _ in provider.stream(req):
                    pass
            assert exc_info.value.code == LLMErrorCode.TIMEOUT
            assert exc_info.value.retryable is True
        finally:
            await provider.close()

    async def test_stream_connect_error(self, config):
        """Connection error during streaming raises LLMError with CONNECTION code."""

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[Message(role=Role.USER, content="Hi")])
            with pytest.raises(LLMError) as exc_info:
                async for _ in provider.stream(req):
                    pass
            assert exc_info.value.code == LLMErrorCode.CONNECTION
            assert exc_info.value.retryable is True
        finally:
            await provider.close()


# ---------------------------------------------------------------------------
# OpenAI provider — extra dict propagation
# ---------------------------------------------------------------------------


class TestOpenAIExtraExtended:
    @pytest.fixture()
    def config(self):
        return LLMConfig(api_key="sk-test", model="gpt-4")

    async def test_extra_fields_in_payload(self, config):
        """Extra dict fields are merged into the request payload."""

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert body["top_p"] == 0.9
            assert body["frequency_penalty"] == 0.3
            return httpx.Response(200, json=_openai_response())

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(
                messages=[Message(role=Role.USER, content="Hi")],
                extra={"top_p": 0.9, "frequency_penalty": 0.3},
            )
            resp = await provider.complete(req)
            assert resp.content == "Hello!"
        finally:
            await provider.close()


# ---------------------------------------------------------------------------
# OpenAI provider — response parsing edge cases
# ---------------------------------------------------------------------------


class TestOpenAIResponseParsing:
    @pytest.fixture()
    def config(self):
        return LLMConfig(api_key="sk-test", model="gpt-4")

    async def test_response_without_usage(self, config):
        """Response with no usage section → usage is None."""
        resp_data = {
            "id": "chatcmpl-test",
            "object": "chat.completion",
            "model": "gpt-4",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "ok"},
                    "finish_reason": "stop",
                }
            ],
        }

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=resp_data)

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[Message(role=Role.USER, content="Hi")])
            resp = await provider.complete(req)
            assert resp.content == "ok"
            assert resp.usage is None
        finally:
            await provider.close()

    async def test_response_finish_reason_length(self, config):
        """finish_reason='length' is correctly propagated."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=_openai_response(finish_reason="length"))

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[Message(role=Role.USER, content="Hi")])
            resp = await provider.complete(req)
            assert resp.finish_reason == "length"
        finally:
            await provider.close()


# ---------------------------------------------------------------------------
# OpenAI provider — SSE parsing edge cases
# ---------------------------------------------------------------------------


class TestOpenAISSEParsing:
    @pytest.fixture()
    def config(self):
        return LLMConfig(api_key="sk-test", model="gpt-4")

    async def test_sse_with_comments(self, config):
        """SSE lines starting with ':' should be skipped."""
        sse = ": keep-alive\n\n" + _sse_lines("Hello")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[Message(role=Role.USER, content="Hi")])
            chunks = [c async for c in provider.stream(req)]
            contents = [c.content for c in chunks if not c.done]
            assert "Hello" in contents
        finally:
            await provider.close()

    async def test_sse_malformed_json_skipped(self, config):
        """Malformed JSON lines in SSE should be silently skipped."""
        sse = "data: {INVALID}\n\n" + _sse_lines("ok")

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[Message(role=Role.USER, content="Hi")])
            chunks = [c async for c in provider.stream(req)]
            contents = [c.content for c in chunks if not c.done]
            assert "ok" in contents
        finally:
            await provider.close()

    async def test_sse_with_usage_in_chunk(self, config):
        """Stream chunk with usage data should expose it."""
        data = {
            "id": "chatcmpl-0",
            "object": "chat.completion.chunk",
            "model": "gpt-4",
            "choices": [{"index": 0, "delta": {"content": "hi"}, "finish_reason": None}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
        }
        sse = f"data: {json.dumps(data)}\n\ndata: [DONE]\n\n"

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, content=sse.encode(), headers={"content-type": "text/event-stream"})

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[Message(role=Role.USER, content="Hi")])
            chunks = [c async for c in provider.stream(req)]
            content_chunks = [c for c in chunks if not c.done]
            assert len(content_chunks) >= 1
            assert content_chunks[0].usage is not None
            assert content_chunks[0].usage.total_tokens == 6
        finally:
            await provider.close()


# ---------------------------------------------------------------------------
# OpenAI provider — close behavior
# ---------------------------------------------------------------------------


class TestOpenAIClose:
    async def test_close_without_requests(self):
        """Closing provider without any requests should not error."""
        cfg = LLMConfig(api_key="sk-test")
        provider = OpenAIProvider(cfg)
        await provider.close()  # should not raise

    async def test_close_twice(self):
        """Calling close twice should not raise."""
        cfg = LLMConfig(api_key="sk-test")
        provider = OpenAIProvider(cfg)
        await provider.close()
        # httpx AsyncClient.aclose() is idempotent
        await provider.close()


# ---------------------------------------------------------------------------
# Provider protocol conformance
# ---------------------------------------------------------------------------


class TestProviderProtocolExtended:
    def test_openai_provider_satisfies_protocol(self):
        cfg = LLMConfig(api_key="test")
        provider = OpenAIProvider(cfg)
        assert isinstance(provider, LLMProvider)

    def test_protocol_has_complete_and_stream(self):
        assert hasattr(LLMProvider, "complete")
        assert hasattr(LLMProvider, "stream")


# ---------------------------------------------------------------------------
# Very long message content
# ---------------------------------------------------------------------------


class TestLargeContent:
    @pytest.fixture()
    def config(self):
        return LLMConfig(api_key="sk-test", model="gpt-4")

    async def test_very_long_message(self, config):
        """128 KB message content should be sent and received correctly."""
        long_content = "A" * 128 * 1024

        def handler(request: httpx.Request) -> httpx.Response:
            body = json.loads(request.content)
            assert len(body["messages"][0]["content"]) == len(long_content)
            return httpx.Response(200, json=_openai_response(content="ok"))

        provider = OpenAIProvider(config, transport=_mock_transport(handler))
        try:
            req = CompletionRequest(messages=[Message(role=Role.USER, content=long_content)])
            resp = await provider.complete(req)
            assert resp.content == "ok"
        finally:
            await provider.close()

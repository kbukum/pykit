"""Tests for common utilities."""

from __future__ import annotations

from pykit_llm_providers.common.errors import (
    APIError,
    ParseAnthropicError,
    ParseGeminiError,
    ParseOpenAIError,
    estimate_tokens,
    parse_error_response,
)


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_text(self):
        assert estimate_tokens("hello world") == 2  # 11 chars // 4

    def test_long_text(self):
        text = "A" * 400
        assert estimate_tokens(text) == 100

    def test_unicode(self):
        text = "こんにちは世界"  # 7 chars
        assert estimate_tokens(text) == 1


class TestParseErrorResponse:
    def test_openai_format(self):
        body = '{"error": {"message": "Invalid API key", "type": "invalid_request_error", "code": "invalid_api_key"}}'
        err = parse_error_response(body, status_code=401)
        assert err.message == "Invalid API key"
        assert err.type == "invalid_request_error"
        assert err.code == "invalid_api_key"
        assert err.status_code == 401

    def test_anthropic_format(self):
        body = '{"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}'
        err = parse_error_response(body, status_code=401)
        assert err.message == "invalid x-api-key"
        assert err.type == "authentication_error"

    def test_plain_text(self):
        err = parse_error_response("Internal Server Error", status_code=500)
        assert err.message == "Internal Server Error"
        assert err.status_code == 500

    def test_bytes_input(self):
        body = b'{"error": {"message": "rate limited"}}'
        err = parse_error_response(body, status_code=429)
        assert err.message == "rate limited"

    def test_empty_body(self):
        err = parse_error_response("", status_code=500)
        assert err.message == ""

    def test_malformed_json(self):
        err = parse_error_response("{bad json}", status_code=500)
        assert err.message == "{bad json}"


class TestAPIError:
    def test_defaults(self):
        err = APIError()
        assert err.message == ""
        assert err.type == ""
        assert err.code == ""
        assert err.status_code == 0

    def test_custom(self):
        err = APIError(
            message="test",
            type="error_type",
            code="error_code",
            status_code=400,
            raw={"key": "value"},
        )
        assert err.message == "test"
        assert err.raw == {"key": "value"}


class TestParseErrors:
    def test_parse_openai_error(self):
        err = ParseOpenAIError("failed to parse")
        assert isinstance(err, Exception)
        assert "failed to parse" in str(err)

    def test_parse_anthropic_error(self):
        err = ParseAnthropicError("unexpected format")
        assert isinstance(err, Exception)

    def test_parse_gemini_error(self):
        err = ParseGeminiError("bad response")
        assert isinstance(err, Exception)

    def test_parse_error_with_api_error(self):
        api_err = APIError(message="detail", status_code=400)
        err = ParseOpenAIError("failed", api_error=api_err)
        assert err.api_error is not None
        assert err.api_error.message == "detail"

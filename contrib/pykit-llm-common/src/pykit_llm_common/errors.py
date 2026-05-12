"""Shared error parsing and token estimation utilities for LLM providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pykit_llm.errors import LLMError, LLMErrorCode


@dataclass
class APIError:
    """Parsed API error from a provider response body."""

    message: str = ""
    type: str = ""
    code: str = ""
    status_code: int = 0
    raw: dict[str, Any] = field(default_factory=dict)


def parse_error_response(body: str | bytes, *, status_code: int = 0) -> APIError:
    """Try to parse a JSON error response body into an APIError.

    Works with OpenAI, Anthropic, and Gemini error formats.
    Returns a best-effort APIError even if parsing fails.
    """
    import json

    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")

    try:
        data = json.loads(body)
    except (json.JSONDecodeError, ValueError):
        return APIError(message=body, status_code=status_code, raw={})

    # OpenAI format: {"error": {"message": ..., "type": ..., "code": ...}}
    if "error" in data and isinstance(data["error"], dict):
        err = data["error"]
        return APIError(
            message=err.get("message", ""),
            type=err.get("type", ""),
            code=str(err.get("code", "")),
            status_code=status_code,
            raw=data,
        )

    # Anthropic format: {"type": "error", "error": {"type": ..., "message": ...}}
    if data.get("type") == "error" and "error" in data:
        err = data["error"]
        return APIError(
            message=err.get("message", ""),
            type=err.get("type", ""),
            status_code=status_code,
            raw=data,
        )

    # Gemini format: {"error": {"message": ..., "status": ..., "code": ...}}
    # (same as OpenAI format, already handled above)

    # Fallback: use any "message" field at the top level
    return APIError(
        message=data.get("message", str(data)),
        status_code=status_code,
        raw=data,
    )


class ParseOpenAIError(LLMError):
    """Error raised when parsing an OpenAI API response fails."""

    def __init__(self, message: str, *, api_error: APIError | None = None) -> None:
        super().__init__(message, code=LLMErrorCode.INVALID_REQUEST)
        self.api_error = api_error


class ParseAnthropicError(LLMError):
    """Error raised when parsing an Anthropic API response fails."""

    def __init__(self, message: str, *, api_error: APIError | None = None) -> None:
        super().__init__(message, code=LLMErrorCode.INVALID_REQUEST)
        self.api_error = api_error


class ParseGeminiError(LLMError):
    """Error raised when parsing a Gemini API response fails."""

    def __init__(self, message: str, *, api_error: APIError | None = None) -> None:
        super().__init__(message, code=LLMErrorCode.INVALID_REQUEST)
        self.api_error = api_error


def estimate_tokens(text: str) -> int:
    """Estimate token count using ~4 characters per token heuristic.

    This is a rough approximation useful for pre-flight checks
    before sending requests to an LLM provider.
    """
    if not text:
        return 0
    return len(text) // 4

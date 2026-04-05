"""LLM error classification mirroring gokit patterns."""

from __future__ import annotations

import enum
from typing import Any

from pykit_errors import AppError
from pykit_errors.codes import ErrorCode as BaseErrorCode


class LLMErrorCode(enum.StrEnum):
    """Classifies LLM client errors."""

    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    INVALID_REQUEST = "invalid_request"
    SERVER = "server"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    STREAM = "stream"


_LLM_CODE_TO_BASE: dict[LLMErrorCode, BaseErrorCode] = {
    LLMErrorCode.AUTH: BaseErrorCode.UNAUTHORIZED,
    LLMErrorCode.RATE_LIMIT: BaseErrorCode.RATE_LIMITED,
    LLMErrorCode.INVALID_REQUEST: BaseErrorCode.INVALID_INPUT,
    LLMErrorCode.SERVER: BaseErrorCode.EXTERNAL_SERVICE,
    LLMErrorCode.TIMEOUT: BaseErrorCode.TIMEOUT,
    LLMErrorCode.CONNECTION: BaseErrorCode.CONNECTION_FAILED,
    LLMErrorCode.STREAM: BaseErrorCode.EXTERNAL_SERVICE,
}


class LLMError(AppError):
    """Structured LLM client error with classification."""

    code: Any  # type: ignore[assignment]

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 0,
        code: LLMErrorCode = LLMErrorCode.SERVER,
        retryable: bool = False,
    ) -> None:
        base_code = _LLM_CODE_TO_BASE.get(code, BaseErrorCode.INTERNAL)
        super().__init__(base_code, message)
        self.status_code = status_code
        self.code = code
        self.retryable = retryable

    def __str__(self) -> str:
        if self.status_code > 0:
            return f"llm: {self.code} (HTTP {self.status_code}): {self.message}"
        return f"llm: {self.code}: {self.message}"


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def auth_error(status_code: int = 401) -> LLMError:
    return LLMError(f"HTTP {status_code}", status_code=status_code, code=LLMErrorCode.AUTH)


def rate_limit_error() -> LLMError:
    return LLMError("HTTP 429", status_code=429, code=LLMErrorCode.RATE_LIMIT, retryable=True)


def server_error(status_code: int = 500) -> LLMError:
    return LLMError(f"HTTP {status_code}", status_code=status_code, code=LLMErrorCode.SERVER, retryable=True)


def stream_error(message: str = "stream failed") -> LLMError:
    return LLMError(message, code=LLMErrorCode.STREAM)


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_status(status_code: int) -> LLMError | None:
    """Map an HTTP status code to a typed LLM error. Returns *None* for 2xx."""
    if 200 <= status_code < 300:
        return None
    if status_code in (401, 403):
        return auth_error(status_code)
    if status_code == 429:
        return rate_limit_error()
    if 400 <= status_code < 500:
        return LLMError(
            f"HTTP {status_code}",
            status_code=status_code,
            code=LLMErrorCode.INVALID_REQUEST,
        )
    if status_code >= 500:
        return server_error(status_code)
    return LLMError(f"HTTP {status_code}", status_code=status_code, code=LLMErrorCode.SERVER)

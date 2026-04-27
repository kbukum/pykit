"""HTTP error classification mirroring gokit's httpclient/errors.go."""

from __future__ import annotations

import enum
from typing import Any

from pykit_errors import AppError
from pykit_errors.codes import ErrorCode as BaseErrorCode


class ErrorCode(enum.StrEnum):
    """Classifies HTTP client errors."""

    TIMEOUT = "timeout"
    CONNECTION = "connection"
    AUTH = "auth"
    NOT_FOUND = "not_found"
    RATE_LIMIT = "rate_limit"
    VALIDATION = "validation"
    SERVER = "server"


_HTTP_CODE_TO_BASE: dict[ErrorCode, BaseErrorCode] = {
    ErrorCode.TIMEOUT: BaseErrorCode.TIMEOUT,
    ErrorCode.CONNECTION: BaseErrorCode.CONNECTION_FAILED,
    ErrorCode.AUTH: BaseErrorCode.UNAUTHORIZED,
    ErrorCode.NOT_FOUND: BaseErrorCode.NOT_FOUND,
    ErrorCode.RATE_LIMIT: BaseErrorCode.RATE_LIMITED,
    ErrorCode.VALIDATION: BaseErrorCode.INVALID_INPUT,
    ErrorCode.SERVER: BaseErrorCode.EXTERNAL_SERVICE,
}


class HttpError(AppError):
    """Structured HTTP client error with classification."""

    code: Any

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 0,
        code: ErrorCode = ErrorCode.SERVER,
        retryable: bool = False,
        body: bytes | None = None,
    ) -> None:
        base_code = _HTTP_CODE_TO_BASE.get(code, BaseErrorCode.INTERNAL)
        super().__init__(base_code, message)
        self.status_code = status_code
        self.code = code
        self.retryable = retryable
        self.body = body

    def __str__(self) -> str:
        if self.status_code > 0:
            return f"httpclient: {self.code} (HTTP {self.status_code}): {self.message}"
        return f"httpclient: {self.code}: {self.message}"


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def timeout_error(message: str = "request timed out") -> HttpError:
    """Create a timeout error."""
    return HttpError(message, code=ErrorCode.TIMEOUT, retryable=True)


def connection_error(message: str = "connection failed") -> HttpError:
    """Create a connection error."""
    return HttpError(message, code=ErrorCode.CONNECTION, retryable=True)


def auth_error(status_code: int = 401, body: bytes | None = None) -> HttpError:
    """Create an authentication/authorization error."""
    return HttpError(
        f"HTTP {status_code}",
        status_code=status_code,
        code=ErrorCode.AUTH,
        retryable=False,
        body=body,
    )


def not_found_error(body: bytes | None = None) -> HttpError:
    """Create a not-found error."""
    return HttpError(
        "HTTP 404",
        status_code=404,
        code=ErrorCode.NOT_FOUND,
        retryable=False,
        body=body,
    )


def rate_limit_error(body: bytes | None = None) -> HttpError:
    """Create a rate-limit error."""
    return HttpError(
        "HTTP 429",
        status_code=429,
        code=ErrorCode.RATE_LIMIT,
        retryable=True,
        body=body,
    )


def validation_error(message: str = "validation failed", body: bytes | None = None) -> HttpError:
    """Create a client-side validation error."""
    return HttpError(
        message,
        code=ErrorCode.VALIDATION,
        retryable=False,
        body=body,
    )


def server_error(status_code: int = 500, body: bytes | None = None) -> HttpError:
    """Create a server error."""
    return HttpError(
        f"HTTP {status_code}",
        status_code=status_code,
        code=ErrorCode.SERVER,
        retryable=True,
        body=body,
    )


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_status(status_code: int, body: bytes | None = None) -> HttpError | None:
    """Classify an HTTP status code into a typed error. Returns None for 2xx."""
    if 200 <= status_code < 300:
        return None
    if status_code in (401, 403):
        return auth_error(status_code, body)
    if status_code == 404:
        return not_found_error(body)
    if status_code == 429:
        return rate_limit_error(body)
    if 400 <= status_code < 500:
        return HttpError(
            f"HTTP {status_code}",
            status_code=status_code,
            code=ErrorCode.VALIDATION,
            retryable=False,
            body=body,
        )
    if status_code >= 500:
        return server_error(status_code, body)
    return HttpError(
        f"HTTP {status_code}",
        status_code=status_code,
        code=ErrorCode.SERVER,
        retryable=False,
        body=body,
    )


def is_retryable(err: BaseException) -> bool:
    """Check if an error is retryable."""
    return isinstance(err, HttpError) and err.retryable

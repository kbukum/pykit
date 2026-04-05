"""Structured error codes with HTTP/gRPC mapping and retryability."""

from __future__ import annotations

from enum import StrEnum


class ErrorCode(StrEnum):
    """Application error codes with protocol mapping."""

    # Connection/availability (retryable)
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    CONNECTION_FAILED = "CONNECTION_FAILED"
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"

    # Resource
    NOT_FOUND = "NOT_FOUND"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    CONFLICT = "CONFLICT"

    # Validation
    INVALID_INPUT = "INVALID_INPUT"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_FORMAT = "INVALID_FORMAT"

    # Auth
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    INVALID_TOKEN = "INVALID_TOKEN"

    # Internal
    INTERNAL = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    EXTERNAL_SERVICE = "EXTERNAL_SERVICE_ERROR"

    @property
    def is_retryable(self) -> bool:
        """Whether operations failing with this code should be retried."""
        return self in _RETRYABLE_CODES

    @property
    def http_status(self) -> int:
        """Corresponding HTTP status code."""
        return _HTTP_STATUS_MAP[self]

    @property
    def grpc_code(self) -> int:
        """Corresponding gRPC status code integer value."""
        return _GRPC_CODE_MAP[self]


_RETRYABLE_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.SERVICE_UNAVAILABLE,
        ErrorCode.CONNECTION_FAILED,
        ErrorCode.TIMEOUT,
        ErrorCode.RATE_LIMITED,
        ErrorCode.EXTERNAL_SERVICE,
    }
)

_HTTP_STATUS_MAP: dict[ErrorCode, int] = {
    ErrorCode.SERVICE_UNAVAILABLE: 503,
    ErrorCode.CONNECTION_FAILED: 502,
    ErrorCode.TIMEOUT: 504,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.ALREADY_EXISTS: 409,
    ErrorCode.CONFLICT: 409,
    ErrorCode.INVALID_INPUT: 422,
    ErrorCode.MISSING_FIELD: 422,
    ErrorCode.INVALID_FORMAT: 422,
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.TOKEN_EXPIRED: 401,
    ErrorCode.INVALID_TOKEN: 401,
    ErrorCode.INTERNAL: 500,
    ErrorCode.DATABASE_ERROR: 500,
    ErrorCode.EXTERNAL_SERVICE: 500,
}

_GRPC_CODE_MAP: dict[ErrorCode, int] = {
    ErrorCode.SERVICE_UNAVAILABLE: 14,  # UNAVAILABLE
    ErrorCode.CONNECTION_FAILED: 14,  # UNAVAILABLE
    ErrorCode.TIMEOUT: 4,  # DEADLINE_EXCEEDED
    ErrorCode.RATE_LIMITED: 8,  # RESOURCE_EXHAUSTED
    ErrorCode.NOT_FOUND: 5,  # NOT_FOUND
    ErrorCode.ALREADY_EXISTS: 6,  # ALREADY_EXISTS
    ErrorCode.CONFLICT: 10,  # ABORTED
    ErrorCode.INVALID_INPUT: 3,  # INVALID_ARGUMENT
    ErrorCode.MISSING_FIELD: 3,  # INVALID_ARGUMENT
    ErrorCode.INVALID_FORMAT: 3,  # INVALID_ARGUMENT
    ErrorCode.UNAUTHORIZED: 16,  # UNAUTHENTICATED
    ErrorCode.TOKEN_EXPIRED: 16,  # UNAUTHENTICATED
    ErrorCode.INVALID_TOKEN: 16,  # UNAUTHENTICATED
    ErrorCode.FORBIDDEN: 7,  # PERMISSION_DENIED
    ErrorCode.INTERNAL: 13,  # INTERNAL
    ErrorCode.DATABASE_ERROR: 13,  # INTERNAL
    ErrorCode.EXTERNAL_SERVICE: 13,  # INTERNAL
}

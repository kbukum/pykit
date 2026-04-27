"""Standard error types with error codes, fluent builders, and gRPC mapping."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any, Self

import grpc

from pykit_errors.codes import ErrorCode

if TYPE_CHECKING:
    from pykit_errors.response import ProblemDetail

# Build reverse map from integer gRPC code to grpc.StatusCode enum member.
_GRPC_STATUS_BY_CODE: dict[int, grpc.StatusCode] = {s.value[0]: s for s in grpc.StatusCode}


class ErrorClassifier(Enum):
    TRANSIENT = "transient"   # client should retry
    PERMANENT = "permanent"   # do not retry
    WRAPPED = "wrapped"       # wraps a third-party error


class AppError(Exception):
    """Base application error with structured error codes and gRPC mapping."""

    def __init__(self, code: ErrorCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = code.is_retryable
        self.http_status = code.http_status
        self.details: dict[str, Any] = {}
        self.cause: Exception | None = None
        self.classifier: ErrorClassifier = ErrorClassifier.PERMANENT

    # Fluent builders

    def with_cause(self, cause: Exception) -> Self:
        """Attach the underlying cause of this error."""
        self.cause = cause
        self.__cause__ = cause  # Python exception chaining
        return self

    def with_detail(self, key: str, value: Any) -> Self:
        """Add a single detail key-value pair."""
        self.details[key] = value
        return self

    def with_details(self, details: dict[str, Any]) -> Self:
        """Merge multiple detail key-value pairs."""
        self.details.update(details)
        return self

    def with_retryable(self, retryable: bool) -> Self:
        """Override the default retryability."""
        self.retryable = retryable
        return self

    # Query helpers

    @property
    def is_retryable(self) -> bool:
        """Whether this error is retryable."""
        return self.retryable

    @property
    def is_not_found(self) -> bool:
        """Whether this is a not-found error."""
        return self.code == ErrorCode.NOT_FOUND

    @property
    def is_unauthorized(self) -> bool:
        """Whether this is an authentication error."""
        return self.code in {ErrorCode.UNAUTHORIZED, ErrorCode.TOKEN_EXPIRED, ErrorCode.INVALID_TOKEN}

    @property
    def is_forbidden(self) -> bool:
        """Whether this is a permission error."""
        return self.code == ErrorCode.FORBIDDEN

    @property
    def is_wrapped(self) -> bool:
        """Whether this error wraps a third-party exception."""
        return self.classifier == ErrorClassifier.WRAPPED

    # Serialization

    def to_problem_detail(self, instance: str = "") -> ProblemDetail:
        """Convert to an RFC 9457 ProblemDetail.

        Args:
            instance: Optional URI reference identifying this specific occurrence.

        Returns:
            A ProblemDetail populated from this error.
        """
        from pykit_errors.response import ProblemDetail

        return ProblemDetail.from_app_error(self, instance=instance)

    # gRPC integration

    def to_grpc_status(self) -> grpc.StatusCode:
        """Convert to the corresponding gRPC status code."""
        return _GRPC_STATUS_BY_CODE[self.code.grpc_code]

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"

    def __repr__(self) -> str:
        return f"AppError({self.code!r}, {self.message!r}, cause={self.cause!r})"

    # Convenience constructors

    @classmethod
    def not_found(cls, resource: str, id: str | None = None) -> Self:
        """Create a NOT_FOUND error for the given resource."""
        msg = f"{resource} not found" if not id else f"{resource} '{id}' not found"
        return cls(ErrorCode.NOT_FOUND, msg).with_detail("resource", resource)

    @classmethod
    def already_exists(cls, resource: str) -> Self:
        """Create an ALREADY_EXISTS error."""
        return cls(ErrorCode.ALREADY_EXISTS, f"{resource} already exists").with_detail("resource", resource)

    @classmethod
    def conflict(cls, reason: str) -> Self:
        """Create a CONFLICT error."""
        return cls(ErrorCode.CONFLICT, reason)

    @classmethod
    def invalid_input(cls, field: str, reason: str) -> Self:
        """Create an INVALID_INPUT error for a specific field."""
        return cls(ErrorCode.INVALID_INPUT, f"Invalid input: {reason}").with_detail("field", field)

    @classmethod
    def missing_field(cls, field: str) -> Self:
        """Create a MISSING_FIELD error."""
        return cls(ErrorCode.MISSING_FIELD, f"Missing required field: {field}").with_detail("field", field)

    @classmethod
    def invalid_format(cls, field: str, expected: str) -> Self:
        """Create an INVALID_FORMAT error."""
        return cls(
            ErrorCode.INVALID_FORMAT, f"Invalid format for {field}. Expected: {expected}"
        ).with_details({"field": field, "expected_format": expected})

    @classmethod
    def unauthorized(cls, reason: str = "") -> Self:
        """Create an UNAUTHORIZED error."""
        return cls(ErrorCode.UNAUTHORIZED, reason or "Authentication required.")

    @classmethod
    def forbidden(cls, reason: str = "") -> Self:
        """Create a FORBIDDEN error."""
        return cls(ErrorCode.FORBIDDEN, reason or "You don't have permission to perform this action.")

    @classmethod
    def token_expired(cls) -> Self:
        """Create a TOKEN_EXPIRED error."""
        return cls(ErrorCode.TOKEN_EXPIRED, "Your session has expired. Please log in again.")

    @classmethod
    def invalid_token(cls) -> Self:
        """Create an INVALID_TOKEN error."""
        return cls(ErrorCode.INVALID_TOKEN, "Invalid authentication token. Please log in again.")

    @classmethod
    def wrap(cls, cause: Exception, message: str = "") -> "AppError":
        """Wrap a third-party exception as an INTERNAL AppError."""
        msg = message or "An unexpected error occurred."
        err = cls(ErrorCode.INTERNAL, msg)
        err.classifier = ErrorClassifier.WRAPPED
        raise err from cause

    @classmethod
    def internal(cls, cause: Exception) -> Self:
        """Create an INTERNAL error wrapping a cause."""
        return cls(ErrorCode.INTERNAL, "An unexpected error occurred.").with_cause(cause)

    @classmethod
    def database_error(cls, cause: Exception) -> Self:
        """Create a DATABASE_ERROR wrapping a cause."""
        return cls(ErrorCode.DATABASE_ERROR, "A database error occurred.").with_cause(cause)

    @classmethod
    def external_service(cls, service: str, cause: Exception | None = None) -> Self:
        """Create an EXTERNAL_SERVICE error."""
        err = cls(
            ErrorCode.EXTERNAL_SERVICE,
            f"The {service} service encountered an error.",
        ).with_detail("service", service)
        if cause:
            err = err.with_cause(cause)
        return err

    @classmethod
    def service_unavailable(cls, service: str) -> Self:
        """Create a SERVICE_UNAVAILABLE error."""
        return cls(ErrorCode.SERVICE_UNAVAILABLE, f"Service '{service}' is unavailable.").with_detail(
            "service", service
        )

    @classmethod
    def connection_failed(cls, service: str) -> Self:
        """Create a CONNECTION_FAILED error."""
        return cls(ErrorCode.CONNECTION_FAILED, f"Unable to connect to {service}.").with_detail(
            "service", service
        )

    @classmethod
    def timeout(cls, operation: str) -> Self:
        """Create a TIMEOUT error."""
        return cls(ErrorCode.TIMEOUT, f"Operation '{operation}' timed out.").with_detail(
            "operation", operation
        )

    @classmethod
    def rate_limited(cls) -> Self:
        """Create a RATE_LIMITED error."""
        return cls(ErrorCode.RATE_LIMITED, "Too many requests. Please wait and try again.")


# Backward-compatible subclasses


class NotFoundError(AppError):
    """Resource not found — maps to gRPC NOT_FOUND."""

    def __init__(self, resource: str, identifier: str = "") -> None:
        msg = f"{resource} not found"
        if identifier:
            msg = f"{resource} '{identifier}' not found"
        super().__init__(ErrorCode.NOT_FOUND, msg)


class InvalidInputError(AppError):
    """Invalid input — maps to gRPC INVALID_ARGUMENT."""

    def __init__(self, message: str, *, field: str = "") -> None:
        super().__init__(ErrorCode.INVALID_INPUT, message)
        if field:
            self.with_detail("field", field)


class ServiceUnavailableError(AppError):
    """Service unavailable — maps to gRPC UNAVAILABLE."""

    def __init__(self, service: str, reason: str = "") -> None:
        msg = f"Service '{service}' is unavailable"
        if reason:
            msg = f"{msg}: {reason}"
        super().__init__(ErrorCode.SERVICE_UNAVAILABLE, msg)


class TimeoutError(AppError):
    """Operation timed out — maps to gRPC DEADLINE_EXCEEDED."""

    def __init__(self, operation: str, timeout_seconds: float) -> None:
        super().__init__(ErrorCode.TIMEOUT, f"Operation '{operation}' timed out after {timeout_seconds}s")

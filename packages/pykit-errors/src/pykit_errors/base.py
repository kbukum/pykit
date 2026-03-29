"""Standard error types with gRPC status code mapping."""

from __future__ import annotations

import grpc


class AppError(Exception):
    """Base application error with gRPC status mapping."""

    grpc_status: grpc.StatusCode = grpc.StatusCode.INTERNAL

    def __init__(self, message: str, *, details: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    """Resource not found — maps to gRPC NOT_FOUND."""

    grpc_status = grpc.StatusCode.NOT_FOUND

    def __init__(self, resource: str, identifier: str = "") -> None:
        msg = f"{resource} not found"
        if identifier:
            msg = f"{resource} '{identifier}' not found"
        super().__init__(msg)


class InvalidInputError(AppError):
    """Invalid input — maps to gRPC INVALID_ARGUMENT."""

    grpc_status = grpc.StatusCode.INVALID_ARGUMENT

    def __init__(self, message: str, *, field: str = "") -> None:
        details = {"field": field} if field else {}
        super().__init__(message, details=details)


class ServiceUnavailableError(AppError):
    """Service unavailable — maps to gRPC UNAVAILABLE."""

    grpc_status = grpc.StatusCode.UNAVAILABLE

    def __init__(self, service: str, reason: str = "") -> None:
        msg = f"Service '{service}' is unavailable"
        if reason:
            msg = f"{msg}: {reason}"
        super().__init__(msg)


class TimeoutError(AppError):
    """Operation timed out — maps to gRPC DEADLINE_EXCEEDED."""

    grpc_status = grpc.StatusCode.DEADLINE_EXCEEDED

    def __init__(self, operation: str, timeout_seconds: float) -> None:
        super().__init__(f"Operation '{operation}' timed out after {timeout_seconds}s")

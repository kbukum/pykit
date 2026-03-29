"""Bidirectional mapping between gRPC status codes and pykit AppError types."""

from __future__ import annotations

import grpc

from pykit_errors import AppError, InvalidInputError, NotFoundError, ServiceUnavailableError
from pykit_errors.base import TimeoutError as AppTimeoutError

# ---------------------------------------------------------------------------
# gRPC status → AppError
# ---------------------------------------------------------------------------

_GRPC_TO_APP: dict[grpc.StatusCode, type[AppError]] = {
    grpc.StatusCode.NOT_FOUND: NotFoundError,
    grpc.StatusCode.INVALID_ARGUMENT: InvalidInputError,
    grpc.StatusCode.UNAVAILABLE: ServiceUnavailableError,
    grpc.StatusCode.DEADLINE_EXCEEDED: AppTimeoutError,
}


def grpc_error_to_app_error(rpc_error: grpc.RpcError) -> AppError:
    """Convert a :class:`grpc.RpcError` to an :class:`AppError`.

    Known status codes are mapped to specific subtypes; everything else
    falls back to a generic :class:`AppError`.
    """
    code: grpc.StatusCode = rpc_error.code()  # type: ignore[union-attr]
    details: str = rpc_error.details()  # type: ignore[union-attr]

    if code == grpc.StatusCode.NOT_FOUND:
        return NotFoundError(resource=details or "resource")

    if code == grpc.StatusCode.INVALID_ARGUMENT:
        return InvalidInputError(details or "invalid argument")

    if code == grpc.StatusCode.UNAVAILABLE:
        return ServiceUnavailableError(service=details or "service")

    if code == grpc.StatusCode.DEADLINE_EXCEEDED:
        return AppTimeoutError(operation=details or "rpc", timeout_seconds=0)

    return AppError(details or f"gRPC error: {code.name}")


# ---------------------------------------------------------------------------
# AppError → gRPC status
# ---------------------------------------------------------------------------

_APP_TO_GRPC: dict[type[AppError], grpc.StatusCode] = {
    NotFoundError: grpc.StatusCode.NOT_FOUND,
    InvalidInputError: grpc.StatusCode.INVALID_ARGUMENT,
    ServiceUnavailableError: grpc.StatusCode.UNAVAILABLE,
    AppTimeoutError: grpc.StatusCode.DEADLINE_EXCEEDED,
}


def app_error_to_grpc_status(app_error: AppError) -> tuple[grpc.StatusCode, str]:
    """Return the ``(StatusCode, message)`` pair for *app_error*.

    Falls back to ``INTERNAL`` for unmapped error types.
    """
    for err_cls, status_code in _APP_TO_GRPC.items():
        if isinstance(app_error, err_cls):
            return status_code, str(app_error)

    # Use the grpc_status attribute if set on the class.
    if hasattr(app_error, "grpc_status") and app_error.grpc_status != grpc.StatusCode.INTERNAL:
        return app_error.grpc_status, str(app_error)

    return grpc.StatusCode.INTERNAL, str(app_error)

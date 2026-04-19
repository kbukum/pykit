"""Standard error types with error codes, fluent builders, and gRPC mapping."""

from __future__ import annotations

from pykit_errors.base import (
    AppError,
    InvalidInputError,
    NotFoundError,
    ServiceUnavailableError,
    TimeoutError,
)
from pykit_errors.codes import ErrorCode
from pykit_errors.response import ProblemDetail, get_type_base_uri, set_type_base_uri

__all__ = [
    "AppError",
    "ErrorCode",
    "InvalidInputError",
    "NotFoundError",
    "ProblemDetail",
    "ServiceUnavailableError",
    "TimeoutError",
    "get_type_base_uri",
    "set_type_base_uri",
]

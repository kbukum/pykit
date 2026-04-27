"""Standard error types with error codes, fluent builders, and gRPC mapping."""

from __future__ import annotations

from pykit_errors.base import (
    AppError,
    ErrorClassifier,
    InvalidInputError,
    NotFoundError,
    ServiceUnavailableError,
    TimeoutError,
)
from pykit_errors.codes import ErrorCode
from pykit_errors.response import ProblemDetail, ProblemDetailFactory, get_type_base_uri, set_type_base_uri

__all__ = [
    "AppError",
    "ErrorClassifier",
    "ErrorCode",
    "InvalidInputError",
    "NotFoundError",
    "ProblemDetail",
    "ProblemDetailFactory",
    "ServiceUnavailableError",
    "TimeoutError",
    "get_type_base_uri",
    "set_type_base_uri",
]

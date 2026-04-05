"""Tests for pykit.errors."""

from __future__ import annotations

import grpc

from pykit_errors import (
    AppError,
    ErrorCode,
    ErrorResponse,
    InvalidInputError,
    NotFoundError,
    ServiceUnavailableError,
)


class TestErrorCode:
    def test_retryable(self) -> None:
        assert ErrorCode.SERVICE_UNAVAILABLE.is_retryable is True
        assert ErrorCode.TIMEOUT.is_retryable is True
        assert ErrorCode.NOT_FOUND.is_retryable is False
        assert ErrorCode.INTERNAL.is_retryable is False

    def test_http_status(self) -> None:
        assert ErrorCode.NOT_FOUND.http_status == 404
        assert ErrorCode.UNAUTHORIZED.http_status == 401
        assert ErrorCode.INTERNAL.http_status == 500
        assert ErrorCode.RATE_LIMITED.http_status == 429

    def test_grpc_code(self) -> None:
        assert ErrorCode.NOT_FOUND.grpc_code == 5
        assert ErrorCode.TIMEOUT.grpc_code == 4
        assert ErrorCode.INTERNAL.grpc_code == 13


class TestAppError:
    def test_basic(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "something went wrong")
        assert "something went wrong" in str(err)
        assert err.message == "something went wrong"
        assert err.code == ErrorCode.INTERNAL
        assert err.details == {}

    def test_fluent_builders(self) -> None:
        cause = ValueError("bad")
        err = (
            AppError(ErrorCode.INTERNAL, "oops")
            .with_cause(cause)
            .with_detail("key", "value")
            .with_retryable(True)
        )
        assert err.cause is cause
        assert err.details == {"key": "value"}
        assert err.is_retryable is True

    def test_with_details(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "bad").with_details({"a": "1", "b": "2"})
        assert err.details == {"a": "1", "b": "2"}

    def test_query_helpers(self) -> None:
        assert AppError(ErrorCode.NOT_FOUND, "x").is_not_found is True
        assert AppError(ErrorCode.UNAUTHORIZED, "x").is_unauthorized is True
        assert AppError(ErrorCode.TOKEN_EXPIRED, "x").is_unauthorized is True
        assert AppError(ErrorCode.FORBIDDEN, "x").is_forbidden is True

    def test_to_grpc_status(self) -> None:
        err = AppError(ErrorCode.NOT_FOUND, "missing")
        assert err.to_grpc_status() == grpc.StatusCode.NOT_FOUND

    def test_str_with_cause(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "failed").with_cause(RuntimeError("boom"))
        assert "cause: boom" in str(err)

    def test_convenience_not_found(self) -> None:
        err = AppError.not_found("User", "abc")
        assert err.code == ErrorCode.NOT_FOUND
        assert "'abc'" in err.message
        assert err.details["resource"] == "User"

    def test_convenience_already_exists(self) -> None:
        err = AppError.already_exists("User")
        assert err.code == ErrorCode.ALREADY_EXISTS

    def test_convenience_invalid_input(self) -> None:
        err = AppError.invalid_input("email", "must be valid")
        assert err.code == ErrorCode.INVALID_INPUT
        assert err.details["field"] == "email"

    def test_convenience_missing_field(self) -> None:
        err = AppError.missing_field("name")
        assert err.code == ErrorCode.MISSING_FIELD

    def test_convenience_unauthorized(self) -> None:
        err = AppError.unauthorized()
        assert err.code == ErrorCode.UNAUTHORIZED
        assert err.http_status == 401

    def test_convenience_internal(self) -> None:
        cause = RuntimeError("db down")
        err = AppError.internal(cause)
        assert err.cause is cause

    def test_convenience_service_unavailable(self) -> None:
        err = AppError.service_unavailable("triton")
        assert err.is_retryable is True
        assert err.details["service"] == "triton"

    def test_convenience_timeout(self) -> None:
        err = AppError.timeout("inference")
        assert err.code == ErrorCode.TIMEOUT
        assert err.is_retryable is True

    def test_convenience_rate_limited(self) -> None:
        err = AppError.rate_limited()
        assert err.code == ErrorCode.RATE_LIMITED
        assert err.is_retryable is True


class TestNotFoundError:
    def test_without_id(self) -> None:
        err = NotFoundError("User")
        assert "User not found" in str(err)
        assert err.code == ErrorCode.NOT_FOUND
        assert err.to_grpc_status() == grpc.StatusCode.NOT_FOUND

    def test_with_id(self) -> None:
        err = NotFoundError("User", "abc-123")
        assert "abc-123" in str(err)


class TestInvalidInputError:
    def test_basic(self) -> None:
        err = InvalidInputError("content cannot be empty")
        assert "content cannot be empty" in str(err)
        assert err.code == ErrorCode.INVALID_INPUT
        assert err.to_grpc_status() == grpc.StatusCode.INVALID_ARGUMENT
        assert err.details == {}

    def test_with_field(self) -> None:
        err = InvalidInputError("must be positive", field="batch_size")
        assert err.details == {"field": "batch_size"}


class TestServiceUnavailableError:
    def test_basic(self) -> None:
        err = ServiceUnavailableError("triton")
        assert "triton" in str(err)
        assert err.code == ErrorCode.SERVICE_UNAVAILABLE
        assert err.to_grpc_status() == grpc.StatusCode.UNAVAILABLE

    def test_with_reason(self) -> None:
        err = ServiceUnavailableError("triton", "connection refused")
        assert "connection refused" in str(err)


class TestErrorResponse:
    def test_from_app_error(self) -> None:
        err = AppError.not_found("User", "abc")
        resp = ErrorResponse.from_app_error(err)
        assert resp.type == "https://pykit.dev/errors/not-found"
        assert resp.title == "NOT_FOUND"
        assert resp.status == 404
        assert resp.detail == err.message

    def test_to_dict(self) -> None:
        resp = ErrorResponse(
            type="https://pykit.dev/errors/internal-error",
            title="INTERNAL_ERROR",
            status=500,
            detail="An unexpected error occurred.",
        )
        d = resp.to_dict()
        assert d["type"] == "https://pykit.dev/errors/internal-error"
        assert d["status"] == 500
        assert "instance" not in d
        assert "extensions" not in d

    def test_to_dict_with_optional_fields(self) -> None:
        resp = ErrorResponse(
            type="https://pykit.dev/errors/not-found",
            title="NOT_FOUND",
            status=404,
            detail="User not found",
            instance="/users/abc",
            extensions={"trace_id": "xyz"},
        )
        d = resp.to_dict()
        assert d["instance"] == "/users/abc"
        assert d["extensions"]["trace_id"] == "xyz"

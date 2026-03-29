"""Tests for pykit.errors."""

from __future__ import annotations

import grpc
from pykit_errors import AppError, InvalidInputError, NotFoundError, ServiceUnavailableError


class TestAppError:
    def test_basic(self) -> None:
        err = AppError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.message == "something went wrong"
        assert err.grpc_status == grpc.StatusCode.INTERNAL
        assert err.details == {}

    def test_with_details(self) -> None:
        err = AppError("bad", details={"key": "value"})
        assert err.details == {"key": "value"}


class TestNotFoundError:
    def test_without_id(self) -> None:
        err = NotFoundError("User")
        assert str(err) == "User not found"
        assert err.grpc_status == grpc.StatusCode.NOT_FOUND

    def test_with_id(self) -> None:
        err = NotFoundError("User", "abc-123")
        assert str(err) == "User 'abc-123' not found"


class TestInvalidInputError:
    def test_basic(self) -> None:
        err = InvalidInputError("content cannot be empty")
        assert str(err) == "content cannot be empty"
        assert err.grpc_status == grpc.StatusCode.INVALID_ARGUMENT
        assert err.details == {}

    def test_with_field(self) -> None:
        err = InvalidInputError("must be positive", field="batch_size")
        assert err.details == {"field": "batch_size"}


class TestServiceUnavailableError:
    def test_basic(self) -> None:
        err = ServiceUnavailableError("triton")
        assert "triton" in str(err)
        assert err.grpc_status == grpc.StatusCode.UNAVAILABLE

    def test_with_reason(self) -> None:
        err = ServiceUnavailableError("triton", "connection refused")
        assert "connection refused" in str(err)

"""Tests for pykit.errors."""

from __future__ import annotations

import grpc
import pytest

from pykit_errors import (
    AppError,
    ErrorCode,
    InvalidInputError,
    NotFoundError,
    ProblemDetail,
    ServiceUnavailableError,
    TimeoutError,
    get_type_base_uri,
    set_type_base_uri,
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


class TestProblemDetail:
    def test_from_app_error(self) -> None:
        err = AppError.not_found("User", "abc")
        pd = ProblemDetail.from_app_error(err)
        assert pd.type == "https://pykit.dev/errors/not-found"
        assert pd.title == "Not Found"
        assert pd.status == 404
        assert pd.detail == err.message
        assert pd.code == "NOT_FOUND"
        assert pd.retryable is False
        assert pd.instance == ""
        assert pd.details == {"resource": "User"}

    def test_from_app_error_with_instance(self) -> None:
        err = AppError.not_found("User", "abc")
        pd = ProblemDetail.from_app_error(err, instance="/api/v1/users/abc")
        assert pd.instance == "/api/v1/users/abc"

    def test_from_app_error_retryable(self) -> None:
        err = AppError.service_unavailable("triton")
        pd = ProblemDetail.from_app_error(err)
        assert pd.retryable is True
        assert pd.code == "SERVICE_UNAVAILABLE"
        assert pd.title == "Service Unavailable"

    def test_from_app_error_internal_error_code(self) -> None:
        err = AppError.internal(ValueError("boom"))
        pd = ProblemDetail.from_app_error(err)
        assert pd.code == "INTERNAL_ERROR"
        assert pd.title == "Internal Error"
        assert pd.type == "https://pykit.dev/errors/internal-error"

    def test_to_dict_minimal(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "broke")
        pd = ProblemDetail.from_app_error(err)
        d = pd.to_dict()
        assert d["type"] == pd.type
        assert d["title"] == pd.title
        assert d["status"] == pd.status
        assert d["detail"] == pd.detail
        assert d["code"] == pd.code
        assert d["retryable"] == pd.retryable
        assert "instance" not in d
        assert "details" not in d

    def test_to_dict_includes_instance_when_set(self) -> None:
        err = AppError.not_found("Widget", "w-1")
        pd = ProblemDetail.from_app_error(err, instance="/api/widgets/w-1")
        assert pd.to_dict()["instance"] == "/api/widgets/w-1"

    def test_to_dict_includes_details_when_set(self) -> None:
        err = AppError.not_found("Widget", "w-1")
        pd = ProblemDetail.from_app_error(err)
        assert pd.to_dict()["details"] == {"resource": "Widget"}

    def test_to_dict_omits_empty_details(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "oops")
        pd = ProblemDetail.from_app_error(err)
        assert "details" not in pd.to_dict()

    def test_frozen_dataclass(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail")
        pd = ProblemDetail.from_app_error(err)
        with pytest.raises(AttributeError):
            pd.type = "changed"  # type: ignore[misc]

    @pytest.mark.parametrize("code", list(ErrorCode))
    def test_from_app_error_all_codes(self, code: ErrorCode) -> None:
        err = AppError(code, "test message")
        pd = ProblemDetail.from_app_error(err)
        expected_kebab = code.value.lower().replace("_", "-")
        assert pd.type == f"https://pykit.dev/errors/{expected_kebab}"
        assert pd.status == code.http_status
        assert pd.detail == "test message"
        assert pd.code == code.value


class TestSetTypeBaseUri:
    def test_custom_base_uri(self) -> None:
        original = get_type_base_uri()
        set_type_base_uri("https://example.com/problems/")
        try:
            err = AppError.not_found("Thing", "t-1")
            pd = ProblemDetail.from_app_error(err)
            assert pd.type.startswith("https://example.com/problems/")
            assert pd.type == "https://example.com/problems/not-found"
        finally:
            set_type_base_uri(original)

    def test_must_end_with_slash(self) -> None:
        with pytest.raises(ValueError, match="must end with '/'"):
            set_type_base_uri("https://example.com/problems")

    def test_get_type_base_uri_returns_default(self) -> None:
        assert get_type_base_uri() == "https://pykit.dev/errors/"


class TestToProblemDetail:
    def test_to_problem_detail(self) -> None:
        err = AppError.not_found("User", "abc")
        pd = err.to_problem_detail()
        assert isinstance(pd, ProblemDetail)
        assert pd.status == 404
        assert pd.code == "NOT_FOUND"

    def test_to_problem_detail_with_instance(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "broken")
        pd = err.to_problem_detail(instance="/api/resource")
        assert pd.instance == "/api/resource"


# ---------------------------------------------------------------------------
# Parametrized: ErrorCode → HTTP status (ALL codes)
# ---------------------------------------------------------------------------

_ALL_HTTP_STATUS_MAP = [
    (ErrorCode.SERVICE_UNAVAILABLE, 503),
    (ErrorCode.CONNECTION_FAILED, 502),
    (ErrorCode.TIMEOUT, 504),
    (ErrorCode.RATE_LIMITED, 429),
    (ErrorCode.NOT_FOUND, 404),
    (ErrorCode.ALREADY_EXISTS, 409),
    (ErrorCode.CONFLICT, 409),
    (ErrorCode.INVALID_INPUT, 422),
    (ErrorCode.MISSING_FIELD, 422),
    (ErrorCode.INVALID_FORMAT, 422),
    (ErrorCode.UNAUTHORIZED, 401),
    (ErrorCode.FORBIDDEN, 403),
    (ErrorCode.TOKEN_EXPIRED, 401),
    (ErrorCode.INVALID_TOKEN, 401),
    (ErrorCode.INTERNAL, 500),
    (ErrorCode.DATABASE_ERROR, 500),
    (ErrorCode.EXTERNAL_SERVICE, 500),
    (ErrorCode.CANCELED, 499),
]


class TestErrorCodeHttpStatusAll:
    @pytest.mark.parametrize(
        "code,expected_status", _ALL_HTTP_STATUS_MAP, ids=lambda v: v if isinstance(v, str) else ""
    )
    def test_http_status_mapping(self, code: ErrorCode, expected_status: int) -> None:
        assert code.http_status == expected_status

    def test_every_error_code_has_http_mapping(self) -> None:
        """Ensure no ErrorCode member is missing from the HTTP map."""
        for code in ErrorCode:
            assert isinstance(code.http_status, int), f"{code} missing HTTP status"


# ---------------------------------------------------------------------------
# Parametrized: ErrorCode → gRPC code (ALL codes)
# ---------------------------------------------------------------------------

_ALL_GRPC_CODE_MAP = [
    (ErrorCode.SERVICE_UNAVAILABLE, 14),
    (ErrorCode.CONNECTION_FAILED, 14),
    (ErrorCode.TIMEOUT, 4),
    (ErrorCode.RATE_LIMITED, 8),
    (ErrorCode.NOT_FOUND, 5),
    (ErrorCode.ALREADY_EXISTS, 6),
    (ErrorCode.CONFLICT, 10),
    (ErrorCode.INVALID_INPUT, 3),
    (ErrorCode.MISSING_FIELD, 3),
    (ErrorCode.INVALID_FORMAT, 3),
    (ErrorCode.UNAUTHORIZED, 16),
    (ErrorCode.TOKEN_EXPIRED, 16),
    (ErrorCode.INVALID_TOKEN, 16),
    (ErrorCode.FORBIDDEN, 7),
    (ErrorCode.INTERNAL, 13),
    (ErrorCode.DATABASE_ERROR, 13),
    (ErrorCode.EXTERNAL_SERVICE, 13),
    (ErrorCode.CANCELED, 1),
]


class TestErrorCodeGrpcCodeAll:
    @pytest.mark.parametrize(
        "code,expected_grpc", _ALL_GRPC_CODE_MAP, ids=lambda v: v if isinstance(v, str) else ""
    )
    def test_grpc_code_mapping(self, code: ErrorCode, expected_grpc: int) -> None:
        assert code.grpc_code == expected_grpc

    def test_every_error_code_has_grpc_mapping(self) -> None:
        for code in ErrorCode:
            assert isinstance(code.grpc_code, int), f"{code} missing gRPC code"


# ---------------------------------------------------------------------------
# Parametrized: ErrorCode.is_retryable (ALL codes)
# ---------------------------------------------------------------------------

_RETRYABLE_CODES = {
    ErrorCode.SERVICE_UNAVAILABLE,
    ErrorCode.CONNECTION_FAILED,
    ErrorCode.TIMEOUT,
    ErrorCode.RATE_LIMITED,
    ErrorCode.EXTERNAL_SERVICE,
}

_ALL_RETRYABLE_MAP = [(code, code in _RETRYABLE_CODES) for code in ErrorCode]


class TestErrorCodeRetryableAll:
    @pytest.mark.parametrize(
        "code,expected", _ALL_RETRYABLE_MAP, ids=lambda v: v if isinstance(v, str) else ""
    )
    def test_is_retryable(self, code: ErrorCode, expected: bool) -> None:
        assert code.is_retryable is expected


# ---------------------------------------------------------------------------
# AppError convenience constructors — detailed assertions
# ---------------------------------------------------------------------------


class TestAppErrorConstructorsDetailed:
    def test_not_found_with_id(self) -> None:
        err = AppError.not_found("user", "123")
        assert err.code == ErrorCode.NOT_FOUND
        assert err.message == "user '123' not found"
        assert err.details["resource"] == "user"
        assert err.http_status == 404
        assert err.is_retryable is False

    def test_not_found_without_id(self) -> None:
        err = AppError.not_found("session")
        assert err.message == "session not found"
        assert err.details["resource"] == "session"

    def test_already_exists(self) -> None:
        err = AppError.already_exists("Account")
        assert err.code == ErrorCode.ALREADY_EXISTS
        assert err.message == "Account already exists"
        assert err.details["resource"] == "Account"
        assert err.http_status == 409

    def test_conflict(self) -> None:
        err = AppError.conflict("version mismatch")
        assert err.code == ErrorCode.CONFLICT
        assert err.message == "version mismatch"
        assert err.details == {}
        assert err.http_status == 409

    def test_invalid_input(self) -> None:
        err = AppError.invalid_input("email", "bad format")
        assert err.code == ErrorCode.INVALID_INPUT
        assert err.message == "Invalid input: bad format"
        assert err.details["field"] == "email"
        assert err.http_status == 422

    def test_missing_field(self) -> None:
        err = AppError.missing_field("username")
        assert err.code == ErrorCode.MISSING_FIELD
        assert err.message == "Missing required field: username"
        assert err.details["field"] == "username"
        assert err.http_status == 422

    def test_invalid_format(self) -> None:
        err = AppError.invalid_format("date", "YYYY-MM-DD")
        assert err.code == ErrorCode.INVALID_FORMAT
        assert "date" in err.message
        assert "YYYY-MM-DD" in err.message
        assert err.details["field"] == "date"
        assert err.details["expected_format"] == "YYYY-MM-DD"
        assert err.http_status == 422

    def test_unauthorized_default(self) -> None:
        err = AppError.unauthorized()
        assert err.code == ErrorCode.UNAUTHORIZED
        assert err.message == "Authentication required."
        assert err.http_status == 401

    def test_unauthorized_custom_reason(self) -> None:
        err = AppError.unauthorized("API key expired")
        assert err.message == "API key expired"

    def test_forbidden_default(self) -> None:
        err = AppError.forbidden()
        assert err.code == ErrorCode.FORBIDDEN
        assert "permission" in err.message.lower()
        assert err.http_status == 403

    def test_forbidden_custom_reason(self) -> None:
        err = AppError.forbidden("Admin only")
        assert err.message == "Admin only"

    def test_token_expired(self) -> None:
        err = AppError.token_expired()
        assert err.code == ErrorCode.TOKEN_EXPIRED
        assert "expired" in err.message.lower()
        assert err.http_status == 401

    def test_invalid_token(self) -> None:
        err = AppError.invalid_token()
        assert err.code == ErrorCode.INVALID_TOKEN
        assert "invalid" in err.message.lower()
        assert err.http_status == 401

    def test_internal(self) -> None:
        cause = RuntimeError("segfault")
        err = AppError.internal(cause)
        assert err.code == ErrorCode.INTERNAL
        assert err.cause is cause
        assert err.http_status == 500

    def test_database_error(self) -> None:
        cause = ConnectionError("pool exhausted")
        err = AppError.database_error(cause)
        assert err.code == ErrorCode.DATABASE_ERROR
        assert err.cause is cause
        assert err.http_status == 500

    def test_external_service_with_cause(self) -> None:
        cause = OSError("dns failure")
        err = AppError.external_service("payment-api", cause)
        assert err.code == ErrorCode.EXTERNAL_SERVICE
        assert err.cause is cause
        assert err.details["service"] == "payment-api"
        assert err.http_status == 500
        assert err.is_retryable is True

    def test_external_service_without_cause(self) -> None:
        err = AppError.external_service("payment-api")
        assert err.cause is None
        assert err.details["service"] == "payment-api"

    def test_service_unavailable(self) -> None:
        err = AppError.service_unavailable("redis")
        assert err.code == ErrorCode.SERVICE_UNAVAILABLE
        assert err.details["service"] == "redis"
        assert err.http_status == 503
        assert err.is_retryable is True

    def test_connection_failed(self) -> None:
        err = AppError.connection_failed("postgres")
        assert err.code == ErrorCode.CONNECTION_FAILED
        assert err.details["service"] == "postgres"
        assert err.http_status == 502
        assert err.is_retryable is True

    def test_timeout(self) -> None:
        err = AppError.timeout("inference")
        assert err.code == ErrorCode.TIMEOUT
        assert err.details["operation"] == "inference"
        assert err.http_status == 504
        assert err.is_retryable is True

    def test_rate_limited(self) -> None:
        err = AppError.rate_limited()
        assert err.code == ErrorCode.RATE_LIMITED
        assert err.http_status == 429
        assert err.is_retryable is True


# ---------------------------------------------------------------------------
# Builder chain tests
# ---------------------------------------------------------------------------


class TestBuilderChains:
    def test_with_cause_preserves_cause(self) -> None:
        cause = ValueError("bad value")
        err = AppError(ErrorCode.INTERNAL, "fail").with_cause(cause)
        assert err.cause is cause

    def test_with_cause_none_initially(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail")
        assert err.cause is None

    def test_with_detail_adds_single_key(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail").with_detail("trace_id", "abc")
        assert err.details == {"trace_id": "abc"}

    def test_with_detail_overwrites_same_key(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail").with_detail("k", "v1").with_detail("k", "v2")
        assert err.details["k"] == "v2"

    def test_with_details_merges(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail").with_detail("a", "1").with_details({"b": "2", "c": "3"})
        assert err.details == {"a": "1", "b": "2", "c": "3"}

    def test_with_details_overwrites_existing(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail").with_detail("a", "old").with_details({"a": "new"})
        assert err.details["a"] == "new"

    def test_with_retryable_overrides_default(self) -> None:
        err = AppError(ErrorCode.NOT_FOUND, "nope").with_retryable(True)
        assert err.is_retryable is True
        assert ErrorCode.NOT_FOUND.is_retryable is False  # code default unchanged

    def test_with_retryable_can_disable(self) -> None:
        err = AppError(ErrorCode.TIMEOUT, "slow").with_retryable(False)
        assert err.is_retryable is False

    def test_full_chain(self) -> None:
        cause = RuntimeError("root")
        err = (
            AppError(ErrorCode.EXTERNAL_SERVICE, "upstream")
            .with_cause(cause)
            .with_detail("url", "https://api.example.com")
            .with_details({"status": "502", "latency_ms": "1200"})
            .with_retryable(False)
        )
        assert err.cause is cause
        assert err.details == {"url": "https://api.example.com", "status": "502", "latency_ms": "1200"}
        assert err.is_retryable is False

    def test_builder_returns_same_instance(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail")
        same = err.with_detail("k", "v")
        assert same is err


# ---------------------------------------------------------------------------
# Error properties — query helpers for ALL relevant codes
# ---------------------------------------------------------------------------


class TestErrorProperties:
    @pytest.mark.parametrize("code", [ErrorCode.NOT_FOUND])
    def test_is_not_found_true(self, code: ErrorCode) -> None:
        assert AppError(code, "x").is_not_found is True

    @pytest.mark.parametrize("code", [c for c in ErrorCode if c != ErrorCode.NOT_FOUND])
    def test_is_not_found_false(self, code: ErrorCode) -> None:
        assert AppError(code, "x").is_not_found is False

    @pytest.mark.parametrize(
        "code",
        [
            ErrorCode.UNAUTHORIZED,
            ErrorCode.TOKEN_EXPIRED,
            ErrorCode.INVALID_TOKEN,
        ],
    )
    def test_is_unauthorized_true(self, code: ErrorCode) -> None:
        assert AppError(code, "x").is_unauthorized is True

    @pytest.mark.parametrize(
        "code",
        [
            c
            for c in ErrorCode
            if c not in {ErrorCode.UNAUTHORIZED, ErrorCode.TOKEN_EXPIRED, ErrorCode.INVALID_TOKEN}
        ],
    )
    def test_is_unauthorized_false(self, code: ErrorCode) -> None:
        assert AppError(code, "x").is_unauthorized is False

    @pytest.mark.parametrize("code", [ErrorCode.FORBIDDEN])
    def test_is_forbidden_true(self, code: ErrorCode) -> None:
        assert AppError(code, "x").is_forbidden is True

    @pytest.mark.parametrize("code", [c for c in ErrorCode if c != ErrorCode.FORBIDDEN])
    def test_is_forbidden_false(self, code: ErrorCode) -> None:
        assert AppError(code, "x").is_forbidden is False


# ---------------------------------------------------------------------------
# to_grpc_status() — parametrized for ALL codes
# ---------------------------------------------------------------------------

_GRPC_STATUS_EXPECTED = [
    (ErrorCode.SERVICE_UNAVAILABLE, grpc.StatusCode.UNAVAILABLE),
    (ErrorCode.CONNECTION_FAILED, grpc.StatusCode.UNAVAILABLE),
    (ErrorCode.TIMEOUT, grpc.StatusCode.DEADLINE_EXCEEDED),
    (ErrorCode.RATE_LIMITED, grpc.StatusCode.RESOURCE_EXHAUSTED),
    (ErrorCode.NOT_FOUND, grpc.StatusCode.NOT_FOUND),
    (ErrorCode.ALREADY_EXISTS, grpc.StatusCode.ALREADY_EXISTS),
    (ErrorCode.CONFLICT, grpc.StatusCode.ABORTED),
    (ErrorCode.INVALID_INPUT, grpc.StatusCode.INVALID_ARGUMENT),
    (ErrorCode.MISSING_FIELD, grpc.StatusCode.INVALID_ARGUMENT),
    (ErrorCode.INVALID_FORMAT, grpc.StatusCode.INVALID_ARGUMENT),
    (ErrorCode.UNAUTHORIZED, grpc.StatusCode.UNAUTHENTICATED),
    (ErrorCode.TOKEN_EXPIRED, grpc.StatusCode.UNAUTHENTICATED),
    (ErrorCode.INVALID_TOKEN, grpc.StatusCode.UNAUTHENTICATED),
    (ErrorCode.FORBIDDEN, grpc.StatusCode.PERMISSION_DENIED),
    (ErrorCode.INTERNAL, grpc.StatusCode.INTERNAL),
    (ErrorCode.DATABASE_ERROR, grpc.StatusCode.INTERNAL),
    (ErrorCode.EXTERNAL_SERVICE, grpc.StatusCode.INTERNAL),
]


class TestToGrpcStatusAll:
    @pytest.mark.parametrize(
        "code,expected_grpc_status", _GRPC_STATUS_EXPECTED, ids=lambda v: v.name if hasattr(v, "name") else ""
    )
    def test_grpc_status(self, code: ErrorCode, expected_grpc_status: grpc.StatusCode) -> None:
        err = AppError(code, "test")
        assert err.to_grpc_status() == expected_grpc_status

    def test_every_code_produces_valid_grpc_status(self) -> None:
        for code in ErrorCode:
            err = AppError(code, "test")
            result = err.to_grpc_status()
            assert isinstance(result, grpc.StatusCode), f"{code} produced {type(result)}"


# ---------------------------------------------------------------------------
# ErrorResponse — comprehensive tests
# ---------------------------------------------------------------------------


class TestProblemDetailComprehensive:
    @pytest.mark.parametrize("code", list(ErrorCode))
    def test_from_app_error_all_codes_type_uri(self, code: ErrorCode) -> None:
        err = AppError(code, "test message")
        pd = ProblemDetail.from_app_error(err)
        expected_kebab = code.value.lower().replace("_", "-")
        assert pd.type == f"https://pykit.dev/errors/{expected_kebab}"
        assert pd.status == code.http_status
        assert pd.detail == "test message"

    def test_to_dict_minimal_keys(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "gone")
        pd = ProblemDetail.from_app_error(err)
        d = pd.to_dict()
        assert {"type", "title", "status", "detail", "code", "retryable"}.issubset(d.keys())
        assert "instance" not in d
        assert "details" not in d

    def test_to_dict_includes_instance_when_set(self) -> None:
        err = AppError.not_found("user", "42")
        pd = ProblemDetail.from_app_error(err, instance="/api/v1/users/42")
        assert pd.to_dict()["instance"] == "/api/v1/users/42"

    def test_to_dict_omits_instance_when_empty(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "oops")
        pd = ProblemDetail.from_app_error(err)
        assert "instance" not in pd.to_dict()

    def test_to_dict_round_trip_structure(self) -> None:
        err = AppError.not_found("Widget", "w-99")
        pd = ProblemDetail.from_app_error(err)
        d = pd.to_dict()
        assert d["type"] == pd.type
        assert d["title"] == pd.title
        assert d["status"] == pd.status
        assert d["detail"] == pd.detail
        assert d["code"] == pd.code
        assert d["retryable"] == pd.retryable

    def test_frozen_dataclass(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail")
        pd = ProblemDetail.from_app_error(err)
        with pytest.raises(AttributeError):
            pd.type = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# __str__ representation
# ---------------------------------------------------------------------------


class TestAppErrorStr:
    def test_str_without_cause(self) -> None:
        err = AppError(ErrorCode.NOT_FOUND, "item missing")
        s = str(err)
        assert "NOT_FOUND" in s
        assert "item missing" in s
        assert "cause" not in s

    def test_str_with_cause(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "broke").with_cause(TypeError("wrong type"))
        s = str(err)
        assert "cause: wrong type" in s

    def test_is_exception(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "boom")
        assert isinstance(err, Exception)

    def test_can_be_raised_and_caught(self) -> None:
        with pytest.raises(AppError) as exc_info:
            raise AppError.not_found("Foo", "1")
        assert exc_info.value.code == ErrorCode.NOT_FOUND


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_string_message(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "")
        assert err.message == ""

    def test_empty_string_in_not_found(self) -> None:
        err = AppError.not_found("", "")
        assert err.code == ErrorCode.NOT_FOUND

    def test_empty_string_unauthorized(self) -> None:
        err = AppError.unauthorized("")
        assert err.message == "Authentication required."

    def test_empty_string_forbidden(self) -> None:
        err = AppError.forbidden("")
        assert err.message == "You don't have permission to perform this action."

    def test_very_long_message(self) -> None:
        long_msg = "x" * 10_000
        err = AppError(ErrorCode.INTERNAL, long_msg)
        assert len(err.message) == 10_000

    def test_unicode_message(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "Ошибка: 数据库连接失败 🔥")
        assert "🔥" in err.message
        assert "Ошибка" in str(err)

    def test_unicode_in_details(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail").with_detail("名前", "テスト")
        assert err.details["名前"] == "テスト"

    def test_special_characters_in_message(self) -> None:
        msg = 'Error: <script>alert("xss")</script> & "quotes" & \'apostrophes\''
        err = AppError(ErrorCode.INTERNAL, msg)
        assert err.message == msg

    def test_details_with_list_value(self) -> None:
        err = AppError(ErrorCode.INVALID_INPUT, "fail").with_detail("fields", ["a", "b", "c"])
        assert err.details["fields"] == ["a", "b", "c"]

    def test_details_with_nested_dict(self) -> None:
        nested = {"inner": {"deep": True, "list": [1, 2]}}
        err = AppError(ErrorCode.INTERNAL, "fail").with_detail("context", nested)
        assert err.details["context"]["inner"]["deep"] is True

    def test_details_with_none_value(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail").with_detail("optional", None)
        assert err.details["optional"] is None

    def test_details_with_numeric_value(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail").with_detail("count", 42)
        assert err.details["count"] == 42

    def test_multiple_with_details_calls_accumulate(self) -> None:
        err = AppError(ErrorCode.INTERNAL, "fail").with_details({"a": 1}).with_details({"b": 2})
        assert err.details == {"a": 1, "b": 2}

    def test_http_status_set_on_init(self) -> None:
        for code in ErrorCode:
            err = AppError(code, "test")
            assert err.http_status == code.http_status


# ---------------------------------------------------------------------------
# Deprecated subclasses
# ---------------------------------------------------------------------------


class TestDeprecatedNotFoundError:
    def test_maps_to_not_found_code(self) -> None:
        err = NotFoundError("Item")
        assert err.code == ErrorCode.NOT_FOUND

    def test_http_status(self) -> None:
        assert NotFoundError("X").http_status == 404

    def test_grpc_status(self) -> None:
        assert NotFoundError("X").to_grpc_status() == grpc.StatusCode.NOT_FOUND

    def test_is_not_found(self) -> None:
        assert NotFoundError("X").is_not_found is True

    def test_is_subclass_of_app_error(self) -> None:
        assert isinstance(NotFoundError("X"), AppError)

    def test_can_be_caught_as_app_error(self) -> None:
        with pytest.raises(AppError):
            raise NotFoundError("Widget", "42")

    def test_with_identifier(self) -> None:
        err = NotFoundError("User", "abc-123")
        assert "abc-123" in err.message

    def test_without_identifier(self) -> None:
        err = NotFoundError("User")
        assert err.message == "User not found"


class TestDeprecatedInvalidInputError:
    def test_maps_to_invalid_input_code(self) -> None:
        err = InvalidInputError("bad data")
        assert err.code == ErrorCode.INVALID_INPUT

    def test_http_status(self) -> None:
        assert InvalidInputError("bad").http_status == 422

    def test_grpc_status(self) -> None:
        assert InvalidInputError("bad").to_grpc_status() == grpc.StatusCode.INVALID_ARGUMENT

    def test_with_field(self) -> None:
        err = InvalidInputError("must be int", field="age")
        assert err.details["field"] == "age"

    def test_without_field(self) -> None:
        err = InvalidInputError("bad")
        assert err.details == {}

    def test_is_subclass_of_app_error(self) -> None:
        assert isinstance(InvalidInputError("x"), AppError)


class TestDeprecatedServiceUnavailableError:
    def test_maps_to_service_unavailable_code(self) -> None:
        err = ServiceUnavailableError("redis")
        assert err.code == ErrorCode.SERVICE_UNAVAILABLE

    def test_http_status(self) -> None:
        assert ServiceUnavailableError("redis").http_status == 503

    def test_grpc_status(self) -> None:
        assert ServiceUnavailableError("redis").to_grpc_status() == grpc.StatusCode.UNAVAILABLE

    def test_is_retryable(self) -> None:
        assert ServiceUnavailableError("redis").is_retryable is True

    def test_with_reason(self) -> None:
        err = ServiceUnavailableError("redis", "connection pool exhausted")
        assert "connection pool exhausted" in err.message

    def test_without_reason(self) -> None:
        err = ServiceUnavailableError("redis")
        assert "redis" in err.message
        assert err.message == "Service 'redis' is unavailable"

    def test_is_subclass_of_app_error(self) -> None:
        assert isinstance(ServiceUnavailableError("x"), AppError)


class TestDeprecatedTimeoutError:
    def test_maps_to_timeout_code(self) -> None:
        err = TimeoutError("query", 30.0)
        assert err.code == ErrorCode.TIMEOUT

    def test_http_status(self) -> None:
        assert TimeoutError("query", 5.0).http_status == 504

    def test_grpc_status(self) -> None:
        assert TimeoutError("query", 5.0).to_grpc_status() == grpc.StatusCode.DEADLINE_EXCEEDED

    def test_is_retryable(self) -> None:
        assert TimeoutError("query", 5.0).is_retryable is True

    def test_message_contains_operation_and_seconds(self) -> None:
        err = TimeoutError("db_query", 12.5)
        assert "db_query" in err.message
        assert "12.5" in err.message

    def test_is_subclass_of_app_error(self) -> None:
        assert isinstance(TimeoutError("op", 1.0), AppError)

    def test_can_be_caught_as_app_error(self) -> None:
        with pytest.raises(AppError):
            raise TimeoutError("slow", 99.0)

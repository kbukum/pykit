# pykit-errors

Standard error types with error codes, fluent builders, RFC 9457 responses, and gRPC status mapping.

## Installation

```bash
pip install pykit-errors
# or
uv add pykit-errors
```

## Quick Start

```python
from pykit_errors import AppError, ErrorCode, ProblemDetail

# Convenience constructors with fluent builders
err = AppError.not_found("User", "abc-123")
err = AppError.unauthorized()
err = AppError.internal(cause=original_exception).with_detail("trace_id", "xyz")

# ErrorCode provides HTTP/gRPC mapping
code = ErrorCode.NOT_FOUND
print(code.http_status)   # 404
print(code.grpc_code)     # 5 (NOT_FOUND)
print(code.is_retryable)  # False

# gRPC integration
grpc_status = err.to_grpc_status()  # grpc.StatusCode.NOT_FOUND

# RFC 9457 error responses
resp = ProblemDetail.from_app_error(err)
resp.to_dict()
# {"type": "https://pykit.dev/errors/not-found", "title": "NOT_FOUND",
#  "status": 404, "detail": "User 'abc-123' not found"}
```

## Key Components

- **ErrorCode** — StrEnum with 18 error codes across 6 categories (connection, resource, validation, auth, internal, lifecycle); each code maps to HTTP status, gRPC code, and retryability via `http_status`, `grpc_code`, and `is_retryable` properties
- **AppError** — Base exception with fluent builder pattern: `with_cause()`, `with_detail()`, `with_details()`, `with_retryable()`; query helpers: `is_retryable`, `is_not_found`, `is_unauthorized`, `is_forbidden`
- **Convenience constructors** — `AppError.not_found()`, `.already_exists()`, `.conflict()`, `.invalid_input()`, `.missing_field()`, `.invalid_format()`, `.unauthorized()`, `.forbidden()`, `.token_expired()`, `.invalid_token()`, `.internal()`, `.database_error()`, `.external_service()`, `.service_unavailable()`, `.connection_failed()`, `.timeout()`, `.rate_limited()`, `.canceled()`
- **ProblemDetail** — Frozen dataclass for RFC 9457 JSON serialization; `from_app_error()` class method and `to_dict()` for API responses
- **to_grpc_status()** — Converts any `AppError` to the corresponding `grpc.StatusCode`
- **NotFoundError / InvalidInputError / ServiceUnavailableError / TimeoutError** — Backward-compatible subclasses for direct instantiation

### Retryable Codes

`SERVICE_UNAVAILABLE`, `CONNECTION_FAILED`, `TIMEOUT`, `RATE_LIMITED`, `EXTERNAL_SERVICE`

## Dependencies

No external dependencies (stdlib only, optional gRPC integration).

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

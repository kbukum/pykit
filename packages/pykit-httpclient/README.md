# pykit-httpclient

Async HTTP client with authentication, bounded redirects, resilience policy integration, and component lifecycle management.

## Installation

```bash
pip install pykit-httpclient
# or
uv add pykit-httpclient
```

## Quick Start

```python
import asyncio
from pykit_httpclient import HttpClient, HttpConfig, AuthConfig, HttpError
from pykit_resilience import PolicyConfig, RetryConfig

config = HttpConfig(
    base_url="https://api.example.com",
    timeout=30.0,
    auth=AuthConfig(type="bearer", token="my-token"),
    resilience=PolicyConfig(retry=RetryConfig(max_attempts=3)),
    max_redirects=5,
)
client = HttpClient(config)

async def main():
    resp = await client.get("/users/123")
    user = resp.json()
    print(user["name"])

    resp = await client.post("/users", body={"name": "Alice"})
    print(resp.status_code, resp.is_success)

    await client.close()

asyncio.run(main())
```

## Key Components

- **HttpClient** — Async HTTP client built on httpx with `get()`, `post()`, `put()`, `patch()`, `delete()` convenience methods and full `request()` for custom needs; handles auth injection, header merging, and automatic error classification
- **HttpConfig** — Configuration: `name`, `base_url`, `timeout`, `headers`, `auth`, `max_retries`, `retry_backoff`, `follow_redirects`
- **AuthConfig** — Authentication config supporting `bearer`, `basic`, and `api_key` types
- **Request** — Outbound request descriptor: `method`, `path`, `headers`, `query`, `body`, `auth`
- **Response** — Result with `status_code`, `headers`, `body`, `is_success`, `is_error`, `json()`, and `text` properties
- **HttpError** — Extends `AppError` with HTTP-specific `status_code`, `code` (ErrorCode), `retryable`, and `body`
- **ErrorCode** — StrEnum classifying errors: `TIMEOUT`, `CONNECTION`, `AUTH`, `NOT_FOUND`, `RATE_LIMIT`, `VALIDATION`, `SERVER`
- **HttpComponent** — Component lifecycle wrapper with health checking via HEAD requests (HEALTHY/DEGRADED/UNHEALTHY)

## Dependencies

- `httpx` — Async HTTP client
- `pykit-errors` — Base error types (`AppError`)
- `pykit-resilience` — Retry and resilience patterns
- `pykit-component` — Component lifecycle protocol

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

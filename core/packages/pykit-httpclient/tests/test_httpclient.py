"""Comprehensive tests for pykit_httpclient."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_httpclient import (
    AuthConfig,
    ErrorCode,
    HttpClient,
    HttpComponent,
    HttpConfig,
    HttpError,
    Request,
    Response,
)
from pykit_httpclient.errors import (
    auth_error,
    classify_status,
    connection_error,
    is_retryable,
    not_found_error,
    rate_limit_error,
    server_error,
    timeout_error,
    validation_error,
)

# ---------------------------------------------------------------------------
# Config defaults
# ---------------------------------------------------------------------------


class TestConfig:
    def test_http_config_defaults(self):
        cfg = HttpConfig()
        assert cfg.name == "httpclient"
        assert cfg.base_url == ""
        assert cfg.timeout == 30.0
        assert cfg.headers == {}
        assert cfg.auth is None
        assert cfg.resilience is None
        assert cfg.follow_redirects is True
        assert cfg.max_redirects == 5

    def test_auth_config_defaults(self):
        auth = AuthConfig()
        assert auth.type == "bearer"
        assert auth.token == ""
        assert auth.username == ""
        assert auth.password == ""
        assert auth.header_name == "X-API-Key"

    def test_http_config_custom(self):
        auth = AuthConfig(type="basic", username="user", password="pass")
        cfg = HttpConfig(
            name="my-api",
            base_url="https://api.example.com",
            timeout=10.0,
            headers={"x-custom": "val"},
            auth=auth,
        )
        assert cfg.name == "my-api"
        assert cfg.base_url == "https://api.example.com"
        assert cfg.timeout == 10.0
        assert cfg.auth is not None
        assert cfg.auth.type == "basic"
        assert cfg.max_redirects == 5


# ---------------------------------------------------------------------------
# Request / Response types
# ---------------------------------------------------------------------------


class TestTypes:
    def test_request_defaults(self):
        req = Request()
        assert req.method == "GET"
        assert req.path == ""
        assert req.headers == {}
        assert req.query == {}
        assert req.body is None
        assert req.auth is None

    def test_response_success(self):
        resp = Response(status_code=200, body=b'{"ok":true}')
        assert resp.is_success is True
        assert resp.is_error is False
        assert resp.json() == {"ok": True}
        assert resp.text == '{"ok":true}'

    def test_response_error(self):
        resp = Response(status_code=404, body=b"not found")
        assert resp.is_success is False
        assert resp.is_error is True
        assert resp.text == "not found"

    def test_response_2xx_range(self):
        for code in (200, 201, 204, 299):
            assert Response(status_code=code).is_success is True
            assert Response(status_code=code).is_error is False

    def test_response_4xx_5xx(self):
        for code in (400, 401, 403, 404, 429, 500, 502, 503):
            assert Response(status_code=code).is_error is True
            assert Response(status_code=code).is_success is False


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------


class TestErrors:
    def test_error_code_values(self):
        assert ErrorCode.TIMEOUT == "timeout"
        assert ErrorCode.CONNECTION == "connection"
        assert ErrorCode.AUTH == "auth"
        assert ErrorCode.NOT_FOUND == "not_found"
        assert ErrorCode.RATE_LIMIT == "rate_limit"
        assert ErrorCode.VALIDATION == "validation"
        assert ErrorCode.SERVER == "server"

    def test_http_error_str_with_status(self):
        err = HttpError("bad", status_code=404, code=ErrorCode.NOT_FOUND)
        assert "HTTP 404" in str(err)
        assert "not_found" in str(err)

    def test_http_error_str_without_status(self):
        err = HttpError("timed out", code=ErrorCode.TIMEOUT)
        assert "timeout" in str(err)
        assert "HTTP" not in str(err).split(": ", 1)[1].split(":")[0]

    def test_http_error_is_app_error(self):
        from pykit_errors import AppError

        err = HttpError("test", code=ErrorCode.SERVER)
        assert isinstance(err, AppError)

    def test_factory_timeout(self):
        err = timeout_error()
        assert err.code == ErrorCode.TIMEOUT
        assert err.retryable is True
        assert err.status_code == 0

    def test_factory_connection(self):
        err = connection_error()
        assert err.code == ErrorCode.CONNECTION
        assert err.retryable is True

    def test_factory_auth(self):
        err = auth_error(403, b"forbidden")
        assert err.code == ErrorCode.AUTH
        assert err.status_code == 403
        assert err.retryable is False
        assert err.body == b"forbidden"

    def test_factory_not_found(self):
        err = not_found_error(b"nope")
        assert err.code == ErrorCode.NOT_FOUND
        assert err.status_code == 404
        assert err.retryable is False

    def test_factory_rate_limit(self):
        err = rate_limit_error()
        assert err.code == ErrorCode.RATE_LIMIT
        assert err.status_code == 429
        assert err.retryable is True

    def test_factory_validation(self):
        err = validation_error("bad input")
        assert err.code == ErrorCode.VALIDATION
        assert err.retryable is False

    def test_factory_server(self):
        err = server_error(502, b"bad gateway")
        assert err.code == ErrorCode.SERVER
        assert err.status_code == 502
        assert err.retryable is True

    # classify_status
    def test_classify_2xx_returns_none(self):
        for code in (200, 201, 204, 299):
            assert classify_status(code) is None

    def test_classify_401(self):
        err = classify_status(401, b"unauth")
        assert err is not None
        assert err.code == ErrorCode.AUTH
        assert err.status_code == 401

    def test_classify_403(self):
        err = classify_status(403)
        assert err is not None
        assert err.code == ErrorCode.AUTH

    def test_classify_404(self):
        err = classify_status(404)
        assert err is not None
        assert err.code == ErrorCode.NOT_FOUND

    def test_classify_429(self):
        err = classify_status(429)
        assert err is not None
        assert err.code == ErrorCode.RATE_LIMIT
        assert err.retryable is True

    def test_classify_400(self):
        err = classify_status(400)
        assert err is not None
        assert err.code == ErrorCode.VALIDATION
        assert err.retryable is False

    def test_classify_422(self):
        err = classify_status(422, b"unprocessable")
        assert err is not None
        assert err.code == ErrorCode.VALIDATION

    def test_classify_500(self):
        err = classify_status(500)
        assert err is not None
        assert err.code == ErrorCode.SERVER
        assert err.retryable is True

    def test_classify_503(self):
        err = classify_status(503)
        assert err is not None
        assert err.code == ErrorCode.SERVER

    # is_retryable
    def test_is_retryable_true(self):
        assert is_retryable(timeout_error()) is True
        assert is_retryable(connection_error()) is True
        assert is_retryable(server_error()) is True
        assert is_retryable(rate_limit_error()) is True

    def test_is_retryable_false(self):
        assert is_retryable(auth_error()) is False
        assert is_retryable(not_found_error()) is False
        assert is_retryable(validation_error()) is False
        assert is_retryable(ValueError("other")) is False


# ---------------------------------------------------------------------------
# HttpClient with mock transport
# ---------------------------------------------------------------------------


def _make_transport(handler):
    """Create an httpx MockTransport from a handler function."""
    return httpx.MockTransport(handler)


class TestHttpClient:
    async def test_get_success(self):
        def handler(request: httpx.Request):
            assert request.method == "GET"
            assert request.url.path == "/users"
            return httpx.Response(200, json={"users": []})

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            resp = await client.get("/users")
            assert resp.status_code == 200
            assert resp.json() == {"users": []}
            assert resp.is_success is True
        finally:
            await client.close()

    async def test_post_with_json_body(self):
        def handler(request: httpx.Request):
            body = json.loads(request.content)
            assert body == {"name": "Alice"}
            return httpx.Response(201, json={"id": 1, "name": "Alice"})

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            resp = await client.post("/users", body={"name": "Alice"})
            assert resp.status_code == 201
            data = resp.json()
            assert data["id"] == 1
        finally:
            await client.close()

    async def test_put(self):
        def handler(request: httpx.Request):
            assert request.method == "PUT"
            return httpx.Response(200, json={"updated": True})

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            resp = await client.put("/items/1", body={"name": "updated"})
            assert resp.status_code == 200
        finally:
            await client.close()

    async def test_patch(self):
        def handler(request: httpx.Request):
            assert request.method == "PATCH"
            return httpx.Response(200, json={"patched": True})

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            resp = await client.patch("/items/1", body={"name": "patched"})
            assert resp.status_code == 200
        finally:
            await client.close()

    async def test_delete(self):
        def handler(request: httpx.Request):
            assert request.method == "DELETE"
            return httpx.Response(204)

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            resp = await client.delete("/items/1")
            assert resp.status_code == 204
        finally:
            await client.close()

    async def test_error_response_raises(self):
        def handler(request: httpx.Request):
            return httpx.Response(404, json={"error": "not found"})

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            with pytest.raises(HttpError) as exc_info:
                await client.get("/missing")
            assert exc_info.value.code == ErrorCode.NOT_FOUND
            assert exc_info.value.status_code == 404
        finally:
            await client.close()

    async def test_server_error_raises(self):
        def handler(request: httpx.Request):
            return httpx.Response(500, text="internal error")

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            with pytest.raises(HttpError) as exc_info:
                await client.get("/broken")
            assert exc_info.value.code == ErrorCode.SERVER
            assert exc_info.value.retryable is True
        finally:
            await client.close()

    async def test_bearer_auth(self):
        def handler(request: httpx.Request):
            auth_header = request.headers.get("authorization")
            assert auth_header == "Bearer my-token"
            return httpx.Response(200, json={"ok": True})

        cfg = HttpConfig(
            base_url="https://api.test",
            auth=AuthConfig(type="bearer", token="my-token"),
        )
        client = HttpClient(cfg, transport=_make_transport(handler))
        try:
            resp = await client.get("/protected")
            assert resp.status_code == 200
        finally:
            await client.close()

    async def test_basic_auth(self):
        import base64

        def handler(request: httpx.Request):
            auth_header = request.headers.get("authorization")
            assert auth_header is not None
            assert auth_header.startswith("Basic ")
            decoded = base64.b64decode(auth_header.split(" ")[1]).decode()
            assert decoded == "user:pass"
            return httpx.Response(200, json={"ok": True})

        cfg = HttpConfig(
            base_url="https://api.test",
            auth=AuthConfig(type="basic", username="user", password="pass"),
        )
        client = HttpClient(cfg, transport=_make_transport(handler))
        try:
            resp = await client.get("/basic")
            assert resp.status_code == 200
        finally:
            await client.close()

    async def test_api_key_auth(self):
        def handler(request: httpx.Request):
            assert request.headers.get("x-api-key") == "secret-key"
            return httpx.Response(200, json={"ok": True})

        cfg = HttpConfig(
            base_url="https://api.test",
            auth=AuthConfig(type="api_key", token="secret-key"),
        )
        client = HttpClient(cfg, transport=_make_transport(handler))
        try:
            resp = await client.get("/api")
            assert resp.status_code == 200
        finally:
            await client.close()

    async def test_request_level_auth_override(self):
        def handler(request: httpx.Request):
            auth_header = request.headers.get("authorization")
            assert auth_header == "Bearer override-token"
            return httpx.Response(200, json={"ok": True})

        cfg = HttpConfig(
            base_url="https://api.test",
            auth=AuthConfig(type="bearer", token="default-token"),
        )
        client = HttpClient(cfg, transport=_make_transport(handler))
        try:
            resp = await client.request(
                Request(
                    method="GET",
                    path="/override",
                    auth=AuthConfig(type="bearer", token="override-token"),
                )
            )
            assert resp.status_code == 200
        finally:
            await client.close()

    async def test_query_params(self):
        def handler(request: httpx.Request):
            assert request.url.params["page"] == "1"
            assert request.url.params["limit"] == "10"
            return httpx.Response(200, json=[])

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            resp = await client.request(
                Request(method="GET", path="/items", query={"page": "1", "limit": "10"})
            )
            assert resp.status_code == 200
        finally:
            await client.close()

    async def test_custom_headers(self):
        def handler(request: httpx.Request):
            assert request.headers.get("x-request-id") == "abc-123"
            return httpx.Response(200, json={"ok": True})

        cfg = HttpConfig(base_url="https://api.test", headers={"x-request-id": "abc-123"})
        client = HttpClient(cfg, transport=_make_transport(handler))
        try:
            resp = await client.get("/headers")
            assert resp.status_code == 200
        finally:
            await client.close()

    async def test_body_bytes(self):
        """Cover client.py line 46: body is bytes."""

        def handler(request: httpx.Request):
            assert request.content == b"raw-bytes"
            return httpx.Response(200)

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            resp = await client.post("/upload", body=b"raw-bytes")
            assert resp.status_code == 200
        finally:
            await client.close()

    async def test_body_string(self):
        """Cover client.py lines 48-49: body is str → content-type set."""

        def handler(request: httpx.Request):
            assert request.headers.get("content-type") == "text/plain"
            return httpx.Response(200)

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            resp = await client.post("/text", body="hello text")
            assert resp.status_code == 200
        finally:
            await client.close()

    async def test_timeout_raises(self):
        """Cover client.py lines 62-63: timeout exception path."""

        def handler(request: httpx.Request):
            raise httpx.ReadTimeout("timed out")

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            with pytest.raises(HttpError) as exc_info:
                await client.get("/slow")
            assert exc_info.value.code == ErrorCode.TIMEOUT
        finally:
            await client.close()

    async def test_connect_error_raises(self):
        """Cover client.py lines 64-65: connect error path."""

        def handler(request: httpx.Request):
            raise httpx.ConnectError("refused")

        client = HttpClient(HttpConfig(base_url="https://api.test"), transport=_make_transport(handler))
        try:
            with pytest.raises(HttpError) as exc_info:
                await client.get("/down")
            assert exc_info.value.code == ErrorCode.CONNECTION
        finally:
            await client.close()

    async def test_config_property(self):
        """Cover client.py line 32: config property."""
        cfg = HttpConfig(base_url="https://api.test")
        client = HttpClient(cfg, transport=_make_transport(lambda r: httpx.Response(200)))
        try:
            assert client.config is cfg
        finally:
            await client.close()


# ---------------------------------------------------------------------------
# HttpComponent lifecycle
# ---------------------------------------------------------------------------


class TestHttpComponent:
    async def test_lifecycle(self):
        cfg = HttpConfig(name="test-http")
        comp = HttpComponent(cfg)

        assert comp.name == "test-http"
        assert comp.client is None

        await comp.start()
        assert comp.client is not None

        health = await comp.health()
        assert health.status.value == "healthy"

        await comp.stop()
        assert comp.client is None

    async def test_health_before_start(self):
        comp = HttpComponent(HttpConfig(name="pre-start"))
        health = await comp.health()
        assert health.status.value == "unhealthy"
        assert "not started" in health.message

    async def test_health_no_base_url(self):
        comp = HttpComponent(HttpConfig(name="no-url", base_url=""))
        await comp.start()
        try:
            health = await comp.health()
            assert health.status.value == "healthy"
        finally:
            await comp.stop()

    async def test_health_with_base_url_success(self):
        """Cover component.py lines 45-48: HEAD returns < 500."""

        def handler(request: httpx.Request):
            return httpx.Response(200)

        cfg = HttpConfig(name="url-check", base_url="https://api.test")
        comp = HttpComponent(cfg)
        await comp.start()
        # Replace the inner httpx client's transport
        comp._client._client = httpx.AsyncClient(
            base_url="https://api.test", transport=_make_transport(handler)
        )
        try:
            health = await comp.health()
            assert health.status.value == "healthy"
        finally:
            await comp.stop()

    async def test_health_with_base_url_degraded(self):
        """Cover component.py lines 49-53: HEAD returns >= 500."""

        def handler(request: httpx.Request):
            return httpx.Response(503)

        cfg = HttpConfig(name="degraded", base_url="https://api.test")
        comp = HttpComponent(cfg)
        await comp.start()
        comp._client._client = httpx.AsyncClient(
            base_url="https://api.test", transport=_make_transport(handler)
        )
        try:
            health = await comp.health()
            assert health.status.value == "degraded"
            assert "503" in health.message
        finally:
            await comp.stop()

    async def test_health_with_base_url_http_error(self):
        """Cover component.py lines 54-55: httpx.HTTPError during health check."""

        def handler(request: httpx.Request):
            raise httpx.ConnectError("refused")

        cfg = HttpConfig(name="error", base_url="https://api.test")
        comp = HttpComponent(cfg)
        await comp.start()
        comp._client._client = httpx.AsyncClient(
            base_url="https://api.test", transport=_make_transport(handler)
        )
        try:
            health = await comp.health()
            assert health.status.value == "unhealthy"
        finally:
            await comp.stop()

    async def test_component_protocol(self):
        from pykit_component import Component

        comp = HttpComponent(HttpConfig())
        assert isinstance(comp, Component)

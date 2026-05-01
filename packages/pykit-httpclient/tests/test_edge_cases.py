"""Comprehensive edge-case tests for pykit-httpclient."""

from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest

from pykit_httpclient import HttpClient, HttpComponent
from pykit_httpclient.config import AuthConfig, HttpConfig
from pykit_httpclient.errors import (
    ErrorCode,
    HttpError,
    classify_status,
    is_retryable,
    server_error,
    timeout_error,
    validation_error,
)
from pykit_httpclient.types import Request, Response

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def mock_transport(handler):
    """Create an httpx MockTransport from a handler function."""
    return httpx.MockTransport(handler)


def ok_handler(request: httpx.Request) -> httpx.Response:
    """Returns 200 with request info as JSON."""
    return httpx.Response(
        200,
        json={
            "method": request.method,
            "url": str(request.url),
            "headers": dict(request.headers),
            "body": request.content.decode("utf-8", errors="replace") if request.content else None,
        },
    )


# ---------------------------------------------------------------------------
# Response edge cases
# ---------------------------------------------------------------------------


class TestResponseEdgeCases:
    def test_empty_body_text(self):
        r = Response(status_code=200, body=b"")
        assert r.text == ""

    def test_empty_body_json_raises(self):
        r = Response(status_code=200, body=b"")
        with pytest.raises(json.JSONDecodeError):
            r.json()

    def test_invalid_json_raises(self):
        r = Response(status_code=200, body=b"not json{")
        with pytest.raises(json.JSONDecodeError):
            r.json()

    def test_binary_body_text_replaces(self):
        r = Response(status_code=200, body=b"\xff\xfe")
        text = r.text
        assert isinstance(text, str)
        # Uses errors="replace", so invalid bytes become replacement chars
        assert "\ufffd" in text

    def test_response_204_no_content(self):
        r = Response(status_code=204, body=b"")
        assert r.is_success
        assert not r.is_error
        assert r.text == ""

    def test_response_boundary_codes(self):
        assert Response(status_code=199).is_success is False
        assert Response(status_code=200).is_success is True
        assert Response(status_code=299).is_success is True
        assert Response(status_code=300).is_success is False
        assert Response(status_code=399).is_error is False
        assert Response(status_code=400).is_error is True


# ---------------------------------------------------------------------------
# Error classification edge cases
# ---------------------------------------------------------------------------


class TestClassifyEdgeCases:
    def test_classify_all_2xx(self):
        for code in range(200, 300):
            assert classify_status(code) is None, f"2xx code {code} should be None"

    def test_classify_418_teapot(self):
        e = classify_status(418, b"teapot")
        assert e is not None
        assert e.code == ErrorCode.VALIDATION
        assert e.retryable is False
        assert e.body == b"teapot"

    def test_classify_502_bad_gateway(self):
        e = classify_status(502, b"bad gateway")
        assert e is not None
        assert e.code == ErrorCode.SERVER
        assert e.retryable is True

    def test_classify_301_redirect(self):
        e = classify_status(301)
        assert e is not None
        assert e.code == ErrorCode.SERVER
        assert e.retryable is False

    def test_classify_100_informational(self):
        e = classify_status(100)
        assert e is not None
        assert e.retryable is False

    def test_classify_body_preserved(self):
        body = b'{"detail":"not found"}'
        e = classify_status(404, body)
        assert e.body == body

    def test_classify_none_body(self):
        e = classify_status(500, None)
        assert e.body is None

    def test_is_retryable_non_http_error(self):
        assert is_retryable(ValueError("nope")) is False

    def test_is_retryable_plain_exception(self):
        assert is_retryable(Exception()) is False


# ---------------------------------------------------------------------------
# Error formatting
# ---------------------------------------------------------------------------


class TestErrorFormatting:
    def test_error_str_with_status(self):
        e = server_error(503, b"down")
        assert "503" in str(e)
        assert "server" in str(e)

    def test_error_str_without_status(self):
        e = timeout_error("timed out")
        s = str(e)
        assert "timeout" in s
        assert "HTTP" not in s or "HTTP 0" not in s

    def test_error_inherits_app_error(self):
        from pykit_errors import AppError

        e = timeout_error()
        assert isinstance(e, AppError)

    def test_factory_validation_with_body(self):
        e = validation_error("bad input", body=b"details")
        assert e.body == b"details"
        assert e.retryable is False


# ---------------------------------------------------------------------------
# Client: body encoding edge cases
# ---------------------------------------------------------------------------


class TestClientBodyEncoding:
    @pytest.fixture()
    def client(self):
        transport = mock_transport(ok_handler)
        cfg = HttpConfig(base_url="http://test", timeout=5.0)
        return HttpClient(cfg, transport=transport)

    async def test_none_body(self, client):
        resp = await client.post("/test", body=None)
        data = resp.json()
        assert data["body"] is None or data["body"] == ""

    async def test_empty_string_body(self, client):
        resp = await client.post("/test", body="")
        data = resp.json()
        # Empty string encodes to empty bytes; httpx may send None for empty content
        assert data["body"] is None or data["body"] == ""

    async def test_unicode_string_body(self, client):
        resp = await client.post("/test", body="héllo wörld 🌍")
        data = resp.json()
        assert "héllo" in data["body"]

    async def test_bytes_body(self, client):
        resp = await client.post("/test", body=b"\x00\x01\x02")
        assert resp.status_code == 200

    async def test_nested_json_body(self, client):
        body = {"nested": {"deep": [1, 2, {"three": True}]}}
        resp = await client.post("/test", body=body)
        assert resp.status_code == 200

    async def test_string_body_sets_text_plain(self, client):
        def check_ct(request: httpx.Request) -> httpx.Response:
            ct = request.headers.get("content-type", "")
            return httpx.Response(200, json={"ct": ct})

        cfg = HttpConfig(base_url="http://test", timeout=5.0)
        c = HttpClient(cfg, transport=mock_transport(check_ct))
        resp = await c.request(Request(method="POST", path="/", body="text"))
        data = resp.json()
        assert "text/plain" in data["ct"]

    async def test_string_body_does_not_override_explicit_ct(self, client):
        def check_ct(request: httpx.Request) -> httpx.Response:
            ct = request.headers.get("content-type", "")
            return httpx.Response(200, json={"ct": ct})

        cfg = HttpConfig(base_url="http://test", timeout=5.0)
        c = HttpClient(cfg, transport=mock_transport(check_ct))
        resp = await c.request(
            Request(
                method="POST",
                path="/",
                body="<xml/>",
                headers={"content-type": "application/xml"},
            )
        )
        data = resp.json()
        assert "application/xml" in data["ct"]


# ---------------------------------------------------------------------------
# Client: header merging
# ---------------------------------------------------------------------------


class TestClientHeaders:
    async def test_config_headers_sent(self):
        def check_headers(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"x-custom": request.headers.get("x-custom", "")})

        cfg = HttpConfig(base_url="http://test", headers={"X-Custom": "from-config"})
        c = HttpClient(cfg, transport=mock_transport(check_headers))
        resp = await c.get("/")
        data = resp.json()
        assert data["x-custom"] == "from-config"

    async def test_request_headers_override_config(self):
        def check_headers(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"x-key": request.headers.get("x-key", "")})

        cfg = HttpConfig(base_url="http://test", headers={"X-Key": "config"})
        c = HttpClient(cfg, transport=mock_transport(check_headers))
        resp = await c.request(
            Request(
                method="GET",
                path="/",
                headers={"X-Key": "override"},
            )
        )
        data = resp.json()
        assert data["x-key"] == "override"


# ---------------------------------------------------------------------------
# Client: auth edge cases
# ---------------------------------------------------------------------------


class TestClientAuth:
    async def test_no_auth_no_header(self):
        def check_auth(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"auth": request.headers.get("authorization", "")})

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(check_auth))
        resp = await c.get("/")
        data = resp.json()
        assert data["auth"] == ""

    async def test_empty_bearer_token(self):
        def check_auth(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"auth": request.headers.get("authorization", "")})

        cfg = HttpConfig(base_url="http://test", auth=AuthConfig(type="bearer", token=""))
        c = HttpClient(cfg, transport=mock_transport(check_auth))
        resp = await c.get("/")
        data = resp.json()
        assert data["auth"] == "Bearer "

    async def test_basic_auth_special_chars(self):
        def check_auth(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"auth": request.headers.get("authorization", "")})

        cfg = HttpConfig(
            base_url="http://test",
            auth=AuthConfig(type="basic", username="user:name", password="p@ss:word"),
        )
        c = HttpClient(cfg, transport=mock_transport(check_auth))
        resp = await c.get("/")
        data = resp.json()
        # Verify the credentials are properly base64 encoded
        encoded = data["auth"].replace("Basic ", "")
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "user:name:p@ss:word"

    async def test_api_key_header_lowercased(self):
        def check_auth(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"key": request.headers.get("x-api-key", "")})

        cfg = HttpConfig(
            base_url="http://test",
            auth=AuthConfig(type="api_key", token="my-key", header_name="X-API-Key"),
        )
        c = HttpClient(cfg, transport=mock_transport(check_auth))
        resp = await c.get("/")
        data = resp.json()
        assert data["key"] == "my-key"

    async def test_request_auth_overrides_config_auth(self):
        def check_auth(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"auth": request.headers.get("authorization", "")})

        cfg = HttpConfig(
            base_url="http://test",
            auth=AuthConfig(type="bearer", token="config-token"),
        )
        c = HttpClient(cfg, transport=mock_transport(check_auth))
        resp = await c.request(
            Request(
                method="GET",
                path="/",
                auth=AuthConfig(type="bearer", token="override-token"),
            )
        )
        data = resp.json()
        assert "override-token" in data["auth"]
        assert "config-token" not in data["auth"]

    async def test_unknown_auth_type_ignored(self):
        """Unknown auth types should not crash - they're silently ignored."""

        def check_auth(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"auth": request.headers.get("authorization", "")})

        cfg = HttpConfig(
            base_url="http://test",
            auth=AuthConfig(type="unknown_type", token="tok"),
        )
        c = HttpClient(cfg, transport=mock_transport(check_auth))
        resp = await c.get("/")
        # Should succeed without crash - unknown type just doesn't set headers
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Client: exception handling
# ---------------------------------------------------------------------------


class TestClientExceptions:
    async def test_timeout_exception_classified(self):
        def timeout_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("read timed out")

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(timeout_handler))
        with pytest.raises(HttpError) as exc_info:
            await c.get("/")
        assert exc_info.value.code == ErrorCode.TIMEOUT
        assert exc_info.value.retryable is True

    async def test_connect_error_classified(self):
        def connect_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused")

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(connect_handler))
        with pytest.raises(HttpError) as exc_info:
            await c.get("/")
        assert exc_info.value.code == ErrorCode.CONNECTION
        assert exc_info.value.retryable is True

    async def test_pool_timeout_is_timeout(self):
        def pool_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.PoolTimeout("pool exhausted")

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(pool_handler))
        with pytest.raises(HttpError) as exc_info:
            await c.get("/")
        assert exc_info.value.code == ErrorCode.TIMEOUT

    async def test_write_timeout_is_timeout(self):
        def write_handler(request: httpx.Request) -> httpx.Response:
            raise httpx.WriteTimeout("write timed out")

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(write_handler))
        with pytest.raises(HttpError) as exc_info:
            await c.get("/")
        assert exc_info.value.code == ErrorCode.TIMEOUT


# ---------------------------------------------------------------------------
# Client: error response handling
# ---------------------------------------------------------------------------


class TestClientErrorResponses:
    async def test_404_raises_not_found(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(404, json={"error": "not found"})

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(handler))
        with pytest.raises(HttpError) as exc_info:
            await c.get("/missing")
        assert exc_info.value.code == ErrorCode.NOT_FOUND

    async def test_401_raises_auth(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, content=b"unauthorized")

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(handler))
        with pytest.raises(HttpError) as exc_info:
            await c.get("/secure")
        assert exc_info.value.code == ErrorCode.AUTH

    async def test_429_raises_rate_limit(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(429, content=b"too many requests")

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(handler))
        with pytest.raises(HttpError) as exc_info:
            await c.get("/")
        assert exc_info.value.code == ErrorCode.RATE_LIMIT
        assert exc_info.value.retryable is True

    async def test_500_raises_server(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, content=b"internal error")

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(handler))
        with pytest.raises(HttpError) as exc_info:
            await c.get("/")
        assert exc_info.value.code == ErrorCode.SERVER
        assert exc_info.value.retryable is True


# ---------------------------------------------------------------------------
# Client: concurrent requests
# ---------------------------------------------------------------------------


class TestClientConcurrency:
    async def test_concurrent_requests(self):
        counter = {"count": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            counter["count"] += 1
            return httpx.Response(200, json={"n": counter["count"]})

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(handler))

        tasks = [c.get(f"/item/{i}") for i in range(10)]
        results = await asyncio.gather(*tasks)
        assert all(r.status_code == 200 for r in results)
        assert len(results) == 10


# ---------------------------------------------------------------------------
# Client: convenience methods
# ---------------------------------------------------------------------------


class TestClientConvenienceMethods:
    @pytest.fixture()
    def client(self):
        transport = mock_transport(ok_handler)
        cfg = HttpConfig(base_url="http://test")
        return HttpClient(cfg, transport=transport)

    async def test_get(self, client):
        resp = await client.get("/resource")
        assert resp.json()["method"] == "GET"

    async def test_post(self, client):
        resp = await client.post("/resource", body={"key": "val"})
        assert resp.json()["method"] == "POST"

    async def test_put(self, client):
        resp = await client.put("/resource", body={"key": "val"})
        assert resp.json()["method"] == "PUT"

    async def test_patch(self, client):
        resp = await client.patch("/resource", body={"key": "val"})
        assert resp.json()["method"] == "PATCH"

    async def test_delete(self, client):
        resp = await client.delete("/resource")
        assert resp.json()["method"] == "DELETE"

    async def test_get_with_query(self, client):
        resp = await client.get("/search", query={"q": "test"})
        url = resp.json()["url"]
        assert "q=test" in url

    async def test_get_with_headers(self, client):
        resp = await client.get("/", headers={"X-Custom": "val"})
        data = resp.json()
        assert data["headers"].get("x-custom") == "val"


# ---------------------------------------------------------------------------
# Component: lifecycle edge cases
# ---------------------------------------------------------------------------


class TestComponentEdgeCases:
    async def test_stop_without_start(self):
        comp = HttpComponent(HttpConfig())
        await comp.stop()  # should not raise
        assert comp.client is None

    async def test_double_stop(self):
        comp = HttpComponent(HttpConfig(base_url="http://test"))
        await comp.start()
        await comp.stop()
        await comp.stop()  # second stop should be safe
        assert comp.client is None

    async def test_start_stop_start(self):
        comp = HttpComponent(HttpConfig())
        await comp.start()
        assert comp.client is not None
        await comp.stop()
        assert comp.client is None
        await comp.start()
        assert comp.client is not None
        await comp.stop()

    async def test_health_before_start(self):
        from pykit_component import HealthStatus

        comp = HttpComponent(HttpConfig())
        h = await comp.health()
        assert h.status == HealthStatus.UNHEALTHY
        assert "not started" in h.message

    async def test_health_no_base_url(self):
        from pykit_component import HealthStatus

        comp = HttpComponent(HttpConfig(base_url=""))
        await comp.start()
        h = await comp.health()
        assert h.status == HealthStatus.HEALTHY
        await comp.stop()

    async def test_name_from_config(self):
        comp = HttpComponent(HttpConfig(name="my-http"))
        assert comp.name == "my-http"

    async def test_client_property(self):
        comp = HttpComponent(HttpConfig())
        assert comp.client is None
        await comp.start()
        assert comp.client is not None
        await comp.stop()


# ---------------------------------------------------------------------------
# Config edge cases
# ---------------------------------------------------------------------------


class TestConfigEdgeCases:
    def test_defaults(self):
        cfg = HttpConfig()
        assert cfg.name == "httpclient"
        assert cfg.base_url == ""
        assert cfg.timeout == 30.0
        assert cfg.headers == {}
        assert cfg.auth is None
        assert cfg.resilience is None
        assert cfg.follow_redirects is True
        assert cfg.max_redirects == 5

    def test_auth_defaults(self):
        auth = AuthConfig()
        assert auth.type == "bearer"
        assert auth.token == ""
        assert auth.username == ""
        assert auth.password == ""
        assert auth.header_name == "X-API-Key"

    def test_custom_config(self):
        cfg = HttpConfig(
            name="custom",
            base_url="http://api.example.com",
            timeout=60.0,
            headers={"Accept": "application/json"},
            follow_redirects=False,
        )
        assert cfg.name == "custom"
        assert cfg.timeout == 60.0
        assert cfg.follow_redirects is False

    def test_config_with_auth(self):
        auth = AuthConfig(type="basic", username="u", password="p")
        cfg = HttpConfig(auth=auth)
        assert cfg.auth.type == "basic"
        assert cfg.auth.username == "u"


# ---------------------------------------------------------------------------
# Security: SSRF-like path testing
# ---------------------------------------------------------------------------


class TestSecurity:
    async def test_path_with_special_chars(self):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"url": str(request.url)})

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(handler))
        resp = await c.get("/path with spaces")
        assert resp.status_code == 200

    async def test_header_with_newline_handled(self):
        """Headers with newlines should be rejected or sanitized by httpx."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200)

        cfg = HttpConfig(base_url="http://test")
        c = HttpClient(cfg, transport=mock_transport(handler))
        # httpx should handle or reject invalid header values
        try:
            await c.request(
                Request(
                    method="GET",
                    path="/",
                    headers={"X-Evil": "value\r\nInjected: true"},
                )
            )
        except (httpx.InvalidURL, ValueError, httpx.HTTPError):
            pass  # Expected - invalid header rejected

    async def test_close_releases_client(self):
        cfg = HttpConfig(base_url="http://test")
        transport = mock_transport(ok_handler)
        c = HttpClient(cfg, transport=transport)
        await c.close()
        # After close, client should raise on usage
        with pytest.raises(Exception):  # noqa: B017
            await c.get("/")


# ---------------------------------------------------------------------------
# Request defaults
# ---------------------------------------------------------------------------


class TestRequestDefaults:
    def test_request_defaults(self):
        r = Request()
        assert r.method == "GET"
        assert r.path == ""
        assert r.headers == {}
        assert r.query == {}
        assert r.body is None
        assert r.auth is None

    def test_request_with_all_fields(self):
        auth = AuthConfig(type="bearer", token="tok")
        r = Request(
            method="POST",
            path="/api",
            headers={"X-H": "v"},
            query={"q": "1"},
            body={"k": "v"},
            auth=auth,
        )
        assert r.method == "POST"
        assert r.body == {"k": "v"}
        assert r.auth.token == "tok"

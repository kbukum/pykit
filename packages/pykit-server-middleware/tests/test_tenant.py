"""Tests for multi-tenant ASGI middleware."""

from __future__ import annotations

import pytest

from pykit_server_middleware.tenant import (
    TenantConfig,
    TenantMiddleware,
    get_tenant,
    require_tenant,
    set_tenant,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_scope(
    *,
    path: str = "/api/test",
    headers: list[tuple[bytes, bytes]] | None = None,
    scope_type: str = "http",
) -> dict:
    return {
        "type": scope_type,
        "method": "GET",
        "path": path,
        "scheme": "http",
        "headers": headers or [],
    }


async def _simple_app(scope, receive, send):
    """Minimal ASGI app that returns 200."""
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"text/plain")],
        }
    )
    await send({"type": "http.response.body", "body": b"OK"})


async def _receive():
    return {"type": "http.request", "body": b""}


async def _collect(lst, msg):
    lst.append(msg)


# ---------------------------------------------------------------------------
# Unit tests — context helpers
# ---------------------------------------------------------------------------


def test_get_tenant_default_none() -> None:
    assert get_tenant() is None


def test_set_and_get_tenant() -> None:
    token = set_tenant("ws-1")
    try:
        assert get_tenant() == "ws-1"
    finally:
        # Reset so other tests aren't affected
        from pykit_server_middleware.tenant import _tenant_var

        _tenant_var.reset(token)


def test_require_tenant_raises() -> None:
    with pytest.raises(RuntimeError, match="No tenant ID set"):
        require_tenant()


def test_require_tenant_returns() -> None:
    from pykit_server_middleware.tenant import _tenant_var

    token = _tenant_var.set("ws-2")
    try:
        assert require_tenant() == "ws-2"
    finally:
        _tenant_var.reset(token)


# ---------------------------------------------------------------------------
# Unit tests — TenantConfig defaults
# ---------------------------------------------------------------------------


def test_tenant_config_defaults() -> None:
    cfg = TenantConfig()
    assert cfg.header_name == "X-Tenant-ID"
    assert cfg.required is True
    assert cfg.skip_paths == frozenset()


def test_tenant_config_custom() -> None:
    cfg = TenantConfig(
        header_name="X-Workspace",
        required=False,
        skip_paths=frozenset({"/healthz"}),
    )
    assert cfg.header_name == "X-Workspace"
    assert cfg.required is False
    assert "/healthz" in cfg.skip_paths


# ---------------------------------------------------------------------------
# Integration tests — TenantMiddleware
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_middleware_sets_tenant() -> None:
    """Middleware extracts tenant from header and sets contextvar."""
    captured: list[str | None] = []

    async def app(scope, receive, send):
        captured.append(get_tenant())
        await _simple_app(scope, receive, send)

    mw = TenantMiddleware(app)
    scope = _make_scope(headers=[(b"x-tenant-id", b"tenant-abc")])
    messages: list[dict] = []
    await mw(scope, _receive, lambda msg: _collect(messages, msg))

    assert captured == ["tenant-abc"]
    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_middleware_resets_tenant_after_request() -> None:
    """Tenant contextvar is reset after the request completes."""

    async def app(scope, receive, send):
        await _simple_app(scope, receive, send)

    mw = TenantMiddleware(app)
    scope = _make_scope(headers=[(b"x-tenant-id", b"t-1")])
    messages: list[dict] = []
    await mw(scope, _receive, lambda msg: _collect(messages, msg))

    assert get_tenant() is None


@pytest.mark.asyncio
async def test_middleware_forbidden_when_required_and_missing() -> None:
    """Returns 403 when tenant header is missing and required=True."""
    mw = TenantMiddleware(_simple_app)
    scope = _make_scope()
    messages: list[dict] = []
    await mw(scope, _receive, lambda msg: _collect(messages, msg))

    assert messages[0]["status"] == 403
    assert b"missing tenant ID" in messages[1]["body"]


@pytest.mark.asyncio
async def test_middleware_allows_missing_when_not_required() -> None:
    """Passes through when tenant header is missing and required=False."""
    cfg = TenantConfig(required=False)
    mw = TenantMiddleware(_simple_app, config=cfg)
    scope = _make_scope()
    messages: list[dict] = []
    await mw(scope, _receive, lambda msg: _collect(messages, msg))

    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_middleware_skips_configured_paths() -> None:
    """Requests to skip_paths bypass tenant extraction."""
    cfg = TenantConfig(skip_paths=frozenset({"/healthz", "/readyz"}))
    mw = TenantMiddleware(_simple_app, config=cfg)
    scope = _make_scope(path="/healthz")
    messages: list[dict] = []
    await mw(scope, _receive, lambda msg: _collect(messages, msg))

    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_middleware_passes_non_http_through() -> None:
    """Non-http/websocket scopes pass through unchanged."""
    mw = TenantMiddleware(_simple_app)
    scope = _make_scope(scope_type="lifespan")
    messages: list[dict] = []
    await mw(scope, _receive, lambda msg: _collect(messages, msg))

    assert messages[0]["status"] == 200


@pytest.mark.asyncio
async def test_middleware_custom_header() -> None:
    """Custom header name is respected."""
    cfg = TenantConfig(header_name="X-Workspace")
    mw = TenantMiddleware(_simple_app, config=cfg)

    # Default header should not work
    scope = _make_scope(headers=[(b"x-tenant-id", b"t-1")])
    messages: list[dict] = []
    await mw(scope, _receive, lambda msg: _collect(messages, msg))
    assert messages[0]["status"] == 403

    # Custom header should work
    captured: list[str | None] = []

    async def capturing_app(scope, receive, send):
        captured.append(get_tenant())
        await _simple_app(scope, receive, send)

    mw2 = TenantMiddleware(capturing_app, config=cfg)
    scope2 = _make_scope(headers=[(b"x-workspace", b"ws-99")])
    messages2: list[dict] = []
    await mw2(scope2, _receive, lambda msg: _collect(messages2, msg))
    assert captured == ["ws-99"]


@pytest.mark.asyncio
async def test_middleware_websocket_scope() -> None:
    """Middleware works for websocket scopes too."""
    captured: list[str | None] = []

    async def app(scope, receive, send):
        captured.append(get_tenant())
        await _simple_app(scope, receive, send)

    mw = TenantMiddleware(app)
    scope = _make_scope(scope_type="websocket", headers=[(b"x-tenant-id", b"ws-tenant")])
    messages: list[dict] = []
    await mw(scope, _receive, lambda msg: _collect(messages, msg))

    assert captured == ["ws-tenant"]

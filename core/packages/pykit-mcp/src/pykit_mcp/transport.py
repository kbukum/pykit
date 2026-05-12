"""MCP transport naming and Streamable HTTP security helpers."""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urlparse

from mcp.server.transport_security import TransportSecuritySettings

from pykit_security import McpHttpSecurityConfig

TRANSPORT_STDIO = "stdio"
TRANSPORT_STREAMABLE_HTTP = "streamable_http"
DEFAULT_ALLOWED_HOSTS = ("localhost", "127.0.0.1", "::1")


def validate_transport_name(name: str) -> str:
    """Validate a canonical MCP transport name."""
    if name not in {TRANSPORT_STDIO, TRANSPORT_STREAMABLE_HTTP}:
        msg = f"unsupported MCP transport {name!r}: use {TRANSPORT_STDIO!r} or {TRANSPORT_STREAMABLE_HTTP!r}"
        raise ValueError(msg)
    return name


def create_streamable_http_security_settings(
    *,
    allowed_hosts: Iterable[str] | None = None,
    allowed_origins: Iterable[str] | None = None,
    enable_dns_rebinding_protection: bool = True,
) -> TransportSecuritySettings:
    """Create Streamable HTTP security settings with loopback-safe defaults."""
    origins = list(allowed_origins or ())
    for origin in origins:
        parsed = urlparse(origin)
        if not parsed.scheme or not parsed.netloc:
            msg = f"invalid allowed origin {origin!r}: expected scheme and host"
            raise ValueError(msg)
        if parsed.scheme not in {"http", "https"}:
            msg = f"invalid allowed origin {origin!r}: scheme must be http or https"
            raise ValueError(msg)
        if parsed.path and parsed.path != "/":
            msg = f"invalid allowed origin {origin!r}: origin must not contain a path"
            raise ValueError(msg)
        if parsed.query or parsed.fragment:
            msg = f"invalid allowed origin {origin!r}: origin must not contain query or fragment"
            raise ValueError(msg)
        if parsed.username or parsed.password:
            msg = f"invalid allowed origin {origin!r}: origin must not contain credentials"
            raise ValueError(msg)
    hosts = list(DEFAULT_ALLOWED_HOSTS if allowed_hosts is None else allowed_hosts)
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=enable_dns_rebinding_protection,
        allowed_hosts=hosts,
        allowed_origins=origins,
    )


def create_mcp_http_security_config(
    *,
    bind_host: str = "127.0.0.1",
    max_payload_bytes: int = 1_048_576,
    allowed_origins: Iterable[str] | None = None,
) -> McpHttpSecurityConfig:
    """Create secure-by-default MCP HTTP helper config."""
    config = McpHttpSecurityConfig(
        bind_host=bind_host,
        max_payload_bytes=max_payload_bytes,
        allowed_origins=tuple(allowed_origins or ()),
    )
    config.validate()
    return config

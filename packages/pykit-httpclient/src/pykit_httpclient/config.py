"""HTTP client configuration."""

from __future__ import annotations

from dataclasses import dataclass, field

from pykit_resilience import PolicyConfig


@dataclass
class AuthConfig:
    """Authentication configuration for HTTP requests."""

    type: str = "bearer"  # "bearer" | "basic" | "api_key"
    token: str = ""
    username: str = ""
    password: str = ""
    header_name: str = "X-API-Key"


@dataclass
class HttpConfig:
    """Configuration for the HTTP client."""

    name: str = "httpclient"
    base_url: str = ""
    timeout: float = 30.0
    headers: dict[str, str] = field(default_factory=dict)
    auth: AuthConfig | None = None
    resilience: PolicyConfig | None = None
    follow_redirects: bool = True
    max_redirects: int = 5

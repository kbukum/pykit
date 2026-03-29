"""HTTP client configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


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
    max_retries: int = 3
    retry_backoff: float = 0.5
    follow_redirects: bool = True

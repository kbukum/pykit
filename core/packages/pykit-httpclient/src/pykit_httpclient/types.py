"""Request and response types."""

from __future__ import annotations

import json as _json
from dataclasses import dataclass, field
from typing import Any

from pykit_httpclient.config import AuthConfig


@dataclass
class Request:
    """Describes an outbound HTTP request."""

    method: str = "GET"
    path: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    query: dict[str, str] = field(default_factory=dict)
    body: Any = None
    auth: AuthConfig | None = None


@dataclass
class Response:
    """Result of an HTTP request."""

    status_code: int = 0
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""

    @property
    def is_success(self) -> bool:
        """True if status code is 2xx."""
        return 200 <= self.status_code < 300

    @property
    def is_error(self) -> bool:
        """True if status code is 4xx or 5xx."""
        return self.status_code >= 400

    def json(self, type_hint: type | None = None) -> Any:
        """Decode the response body as JSON."""
        return _json.loads(self.body)

    @property
    def text(self) -> str:
        """Return the response body as a string."""
        return self.body.decode("utf-8", errors="replace")

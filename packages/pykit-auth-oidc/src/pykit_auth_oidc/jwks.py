"""JWKS cache with TTL-based refresh for OIDC token verification."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class JWKSCache:
    """Caches JWKS keys with TTL-based refresh.

    Args:
        jwks_uri: The JWKS endpoint URI.
        ttl_seconds: How long to cache keys before refreshing. Defaults to 3600 (1 hour).
        http_timeout: HTTP request timeout in seconds. Defaults to 10.
    """

    jwks_uri: str
    ttl_seconds: int = 3600
    http_timeout: float = 10.0
    _keys: dict[str, Any] = field(default_factory=dict, init=False, repr=False)
    _fetched_at: float = field(default=0.0, init=False, repr=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)

    async def get_keys(self) -> dict[str, Any]:
        """Return cached JWKS keys, refreshing if TTL has expired."""
        if time.monotonic() - self._fetched_at > self.ttl_seconds:
            await self._refresh()
        return self._keys

    async def _refresh(self) -> None:
        async with self._lock:
            # Double-check after acquiring lock
            if time.monotonic() - self._fetched_at <= self.ttl_seconds:
                return
            import httpx

            async with httpx.AsyncClient(timeout=self.http_timeout) as client:
                resp = await client.get(self.jwks_uri)
                resp.raise_for_status()
                self._keys = resp.json()
                self._fetched_at = time.monotonic()

    async def invalidate(self) -> None:
        """Force a refresh on the next ``get_keys`` call."""
        async with self._lock:
            self._fetched_at = 0.0

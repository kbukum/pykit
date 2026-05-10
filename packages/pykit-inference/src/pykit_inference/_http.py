"""Shared HTTP client helpers for inference adapters."""

from __future__ import annotations

import httpx

from pykit_httpclient import HttpClient, HttpConfig, HttpError
from pykit_inference.errors import InferenceError, InferenceHTTPError

type InferenceHttpClient = HttpClient | httpx.AsyncClient


def build_http_client(
    *,
    name: str,
    base_url: str,
    timeout: float,
    client: InferenceHttpClient | None,
) -> tuple[HttpClient, bool]:
    """Return a canonical HTTP client plus ownership flag."""
    config = HttpConfig(name=name, base_url=base_url, timeout=timeout)
    if isinstance(client, HttpClient):
        return client, False
    if isinstance(client, httpx.AsyncClient):
        return HttpClient(config, client=client), False
    return HttpClient(config), True


def map_http_error(exc: HttpError) -> InferenceError:
    """Translate canonical HTTP client failures into inference errors."""
    if exc.status_code > 0:
        message = exc.body.decode("utf-8", errors="replace") if exc.body is not None else exc.message
        return InferenceHTTPError(exc.status_code, message)
    return InferenceError(str(exc))

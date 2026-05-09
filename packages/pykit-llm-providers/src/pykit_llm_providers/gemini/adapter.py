"""Gemini adapter factory — bridges GeminiConfig to pykit-llm with httpclient auth."""

from __future__ import annotations

from pykit_httpclient import HttpClient, HttpConfig
from pykit_llm_providers.gemini.config import GeminiConfig
from pykit_llm_providers.gemini.dialect import GeminiProvider


def new_adapter(config: GeminiConfig) -> GeminiProvider:
    """Create a Gemini provider with proper pykit-httpclient setup.

    Gemini API key is sent via the ``x-goog-api-key`` header (never in the
    query string). The adapter wires the canonical pykit HttpClient base URL
    and timeout into the underlying httpx client.
    """
    http_config = HttpConfig(
        name="gemini",
        base_url=config.base_url or "https://generativelanguage.googleapis.com",
        timeout=config.timeout,
    )
    client = HttpClient(http_config)
    provider = GeminiProvider.__new__(GeminiProvider)
    provider._config = config
    provider._client = client._client
    if config.api_key:
        provider._client.headers["x-goog-api-key"] = config.api_key
    return provider

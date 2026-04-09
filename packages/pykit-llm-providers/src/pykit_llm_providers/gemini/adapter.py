"""Gemini adapter factory — bridges GeminiConfig to pykit-llm with httpclient auth."""

from __future__ import annotations

from pykit_httpclient import HttpClient, HttpConfig
from pykit_llm_providers.gemini.config import GeminiConfig
from pykit_llm_providers.gemini.dialect import GeminiProvider


def new_adapter(config: GeminiConfig) -> GeminiProvider:
    """Create a Gemini provider with proper pykit-httpclient setup.

    Gemini uses API key via query parameter, not headers.
    The adapter configures the HttpClient base URL and timeout.
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
    return provider

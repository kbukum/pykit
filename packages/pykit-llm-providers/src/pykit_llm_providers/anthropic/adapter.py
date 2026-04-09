"""Anthropic adapter factory — bridges AnthropicConfig to pykit-llm with httpclient auth."""

from __future__ import annotations

from pykit_httpclient import AuthConfig, HttpClient, HttpConfig
from pykit_llm_providers.anthropic.config import AnthropicConfig
from pykit_llm_providers.anthropic.dialect import AnthropicProvider


def new_adapter(config: AnthropicConfig) -> AnthropicProvider:
    """Create an Anthropic provider with proper pykit-httpclient auth.

    Uses api_key header (x-api-key) and version header (anthropic-version)
    via pykit-httpclient AuthConfig.
    """
    http_config = HttpConfig(
        name="anthropic",
        base_url=config.base_url or "https://api.anthropic.com",
        timeout=config.timeout,
        auth=AuthConfig(type="api_key", token=config.api_key, header_name="x-api-key"),
        headers={"anthropic-version": config.api_version},
    )
    client = HttpClient(http_config)
    provider = AnthropicProvider.__new__(AnthropicProvider)
    from pykit_llm.config import LLMConfig

    provider._config = config
    provider._llm_config = LLMConfig(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        timeout=config.timeout,
    )
    provider._client = client._client
    return provider

"""OpenAI adapter factory — bridges OpenAIConfig to pykit-llm Adapter with httpclient auth."""

from __future__ import annotations

from pykit_httpclient import AuthConfig, HttpClient, HttpConfig
from pykit_llm_providers.openai.config import OpenAIConfig
from pykit_llm_providers.openai.dialect import OpenAIProvider


def new_adapter(config: OpenAIConfig) -> OpenAIProvider:
    """Create an OpenAI provider with proper pykit-httpclient BearerAuth.

    Bridges OpenAIConfig into an OpenAIProvider that uses pykit-httpclient
    AuthConfig for authentication instead of raw httpx headers.
    """
    http_config = HttpConfig(
        name="openai",
        base_url=config.base_url or "https://api.openai.com/v1",
        timeout=config.timeout,
        auth=AuthConfig(type="bearer", token=config.api_key),
    )
    client = HttpClient(http_config)
    provider = OpenAIProvider.__new__(OpenAIProvider)
    from pykit_llm.config import LLMConfig

    provider._config = LLMConfig(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model,
        timeout=config.timeout,
    )
    provider._client = client._client
    return provider

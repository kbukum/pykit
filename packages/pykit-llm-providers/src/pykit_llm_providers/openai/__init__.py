"""OpenAI-compatible LLM and embedding provider."""

from pykit_llm_providers.openai.adapter import new_adapter
from pykit_llm_providers.openai.config import OpenAIConfig
from pykit_llm_providers.openai.dialect import OpenAIProvider
from pykit_llm_providers.openai.embedding import OpenAIEmbeddingProvider

__all__ = [
    "OpenAIConfig",
    "OpenAIEmbeddingProvider",
    "OpenAIProvider",
    "new_adapter",
]

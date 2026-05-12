"""OpenAI-compatible LLM and embedding provider."""

from pykit_llm_openai.adapter import new_adapter
from pykit_llm_openai.config import OpenAIConfig
from pykit_llm_openai.dialect import OpenAIProvider
from pykit_llm_openai.embedding import OpenAIEmbeddingProvider

__all__ = [
    "OpenAIConfig",
    "OpenAIEmbeddingProvider",
    "OpenAIProvider",
    "new_adapter",
]

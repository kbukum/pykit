"""Unified OpenAI configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class OpenAIConfig:
    """Configuration for OpenAI-compatible LLM and embedding services.

    Works with OpenAI, Azure OpenAI, local llama.cpp, vLLM, or any server
    that exposes ``/v1/chat/completions`` and ``/v1/embeddings`` endpoints.
    """

    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    timeout: float = 120.0

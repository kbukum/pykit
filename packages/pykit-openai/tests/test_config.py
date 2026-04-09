"""Tests for OpenAI unified configuration."""

from __future__ import annotations

from pykit_openai.config import OpenAIConfig


class TestOpenAIConfig:
    def test_defaults(self):
        cfg = OpenAIConfig()
        assert cfg.base_url == "https://api.openai.com/v1"
        assert cfg.api_key == ""
        assert cfg.model == "gpt-4o"
        assert cfg.embedding_model == "text-embedding-3-small"
        assert cfg.embedding_dimensions == 1536
        assert cfg.timeout == 120.0

    def test_custom(self):
        cfg = OpenAIConfig(
            base_url="https://my.endpoint.com/v1",
            api_key="sk-test",
            model="gpt-4o-mini",
            embedding_model="text-embedding-ada-002",
            embedding_dimensions=768,
            timeout=30.0,
        )
        assert cfg.base_url == "https://my.endpoint.com/v1"
        assert cfg.api_key == "sk-test"
        assert cfg.model == "gpt-4o-mini"
        assert cfg.embedding_model == "text-embedding-ada-002"
        assert cfg.embedding_dimensions == 768
        assert cfg.timeout == 30.0

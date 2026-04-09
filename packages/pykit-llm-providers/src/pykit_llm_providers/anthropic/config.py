"""Anthropic API configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AnthropicConfig:
    """Configuration for the Anthropic Claude API.

    See https://docs.anthropic.com/en/api for documentation.
    """

    base_url: str = "https://api.anthropic.com"
    api_key: str = ""
    model: str = "claude-sonnet-4-20250514"
    api_version: str = "2023-06-01"
    timeout: float = 120.0
    max_tokens: int = 4096

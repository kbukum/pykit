"""Google Gemini API configuration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GeminiConfig:
    """Configuration for the Google Generative AI (Gemini) API.

    See https://ai.google.dev/api for documentation.
    """

    base_url: str = "https://generativelanguage.googleapis.com"
    api_key: str = ""
    model: str = "gemini-2.0-flash"
    timeout: float = 120.0
    max_output_tokens: int = 4096

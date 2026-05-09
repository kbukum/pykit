"""vLLM OAI-compatible text completions adapter."""

from __future__ import annotations

from pykit_inference.vllm.client import VLLMConfig, VLLMInference
from pykit_inference.vllm.register import register

__all__ = ["VLLMConfig", "VLLMInference", "register"]

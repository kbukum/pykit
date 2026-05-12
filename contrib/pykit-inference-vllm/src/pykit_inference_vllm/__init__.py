"""vLLM OAI-compatible text completions adapter."""

from __future__ import annotations

from pykit_inference_vllm.client import VLLMConfig, VLLMInference
from pykit_inference_vllm.register import register

__all__ = ["VLLMConfig", "VLLMInference", "register"]

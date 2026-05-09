"""Explicit vLLM adapter registry wiring."""

from __future__ import annotations

from typing import Any

from pykit_inference.registry import Registry
from pykit_inference.vllm.client import VLLMConfig, VLLMInference

VLLM_KIND = "vllm"


def register(reg: Registry) -> None:
    """Register the vLLM OAI-compat adapter factory."""
    reg.register(VLLM_KIND, _build)


def _build(config: dict[str, Any]) -> VLLMInference:
    vllm_config = VLLMConfig.model_validate(config)
    return VLLMInference(vllm_config)

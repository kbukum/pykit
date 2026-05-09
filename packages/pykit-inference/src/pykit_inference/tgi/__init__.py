"""Text Generation Inference OAI-compatible chat completions adapter."""

from __future__ import annotations

from pykit_inference.tgi.client import TGIConfig, TGIInference
from pykit_inference.tgi.register import register

__all__ = ["TGIConfig", "TGIInference", "register"]

"""Triton KServe v2 inference adapter."""

from __future__ import annotations

from pykit_inference_triton.client import TritonInference
from pykit_inference_triton.register import register

__all__ = ["TritonInference", "register"]

"""Triton KServe v2 inference adapter."""

from __future__ import annotations

from pykit_inference.triton.client import TritonInference
from pykit_inference.triton.register import register

__all__ = ["TritonInference", "register"]

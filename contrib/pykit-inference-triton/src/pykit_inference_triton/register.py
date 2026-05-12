"""Explicit Triton adapter registry wiring."""

from __future__ import annotations

from typing import Any

from pykit_inference.registry import Registry
from pykit_inference_triton.client import TritonConfig, TritonInference

TRITON_KIND = "triton"


def register(reg: Registry) -> None:
    """Register the Triton KServe v2 adapter factory."""
    reg.register(TRITON_KIND, _build)


def _build(config: dict[str, Any]) -> TritonInference:
    triton_config = TritonConfig.model_validate(config)
    return TritonInference(triton_config)

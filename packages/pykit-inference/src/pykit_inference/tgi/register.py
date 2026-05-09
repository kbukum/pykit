"""Explicit Text Generation Inference adapter registry wiring."""

from __future__ import annotations

from typing import Any

from pykit_inference.registry import Registry
from pykit_inference.tgi.client import TGIConfig, TGIInference

TGI_KIND = "tgi"


def register(reg: Registry) -> None:
    """Register the Text Generation Inference OAI-compat adapter factory."""
    reg.register(TGI_KIND, _build)


def _build(config: dict[str, Any]) -> TGIInference:
    tgi_config = TGIConfig.model_validate(config)
    return TGIInference(tgi_config)

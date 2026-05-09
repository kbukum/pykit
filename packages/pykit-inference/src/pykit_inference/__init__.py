"""pykit-inference — model-serving runtime adapter layer.

This package owns prediction contracts for model-serving runtimes (Triton,
vLLM raw, TGI, KServe v2, BentoML, ONNX Runtime Server, TFServing, and custom
REST/gRPC). Chat completion APIs belong to ``pykit_llm``.
"""

from __future__ import annotations

from pykit_inference.echo import ECHO_KIND, Echo
from pykit_inference.errors import InferenceAuthorizationError, InferenceError, InferenceHTTPError
from pykit_inference.registry import Registry
from pykit_inference.triton import TritonInference
from pykit_inference.types import (
    ChunkEvent,
    Error,
    Inference,
    InferenceDescriptor,
    MessageStart,
    MessageStop,
    PredictRequest,
    PredictResponse,
    PredictStatus,
    ReasoningDelta,
    StreamEvent,
    StreamingInference,
    Tensor,
    TextDelta,
    ToolUseDelta,
    Usage,
    UsageDelta,
    Value,
    ValueKind,
)

__all__ = [
    "ChunkEvent",
    "ECHO_KIND",
    "Echo",
    "TextDelta",
    "Inference",
    "InferenceAuthorizationError",
    "InferenceDescriptor",
    "InferenceError",
    "InferenceHTTPError",
    "MessageStop",
    "MessageStart",
    "PredictRequest",
    "PredictResponse",
    "PredictStatus",
    "ReasoningDelta",
    "Registry",
    "Error",
    "StreamEvent",
    "StreamingInference",
    "Tensor",
    "ToolUseDelta",
    "TritonInference",
    "Usage",
    "UsageDelta",
    "Value",
    "ValueKind",
]

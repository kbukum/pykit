"""Deterministic echo inference adapter."""

from __future__ import annotations

from pykit_ai import Model, Provider, Usage
from pykit_inference.registry import Registry
from pykit_inference.types import InferenceDescriptor, PredictRequest, PredictResponse
from pykit_tool import Envelope

ECHO_KIND = "echo"


class Echo:
    """Lean default adapter that returns request inputs unchanged."""

    def __init__(self, *, name: str = ECHO_KIND) -> None:
        self._descriptor = InferenceDescriptor(
            name=name,
            description="Echo inference adapter for tests and local wiring",
            serving_protocol="echo",
            envelope=Envelope(scopes=("inference:predict",)),
        )

    def descriptor(self) -> InferenceDescriptor:
        """Return adapter descriptor and executable envelope."""
        return self._descriptor

    async def predict(self, request: PredictRequest) -> PredictResponse:
        """Return inputs unchanged with default usage and echo model identity."""
        return PredictResponse(
            outputs=dict(request.inputs),
            usage=Usage(),
            model=Model(
                name=request.model_name,
                provider=Provider.CUSTOM,
                version=request.model_version or "",
            ),
        )


def register(reg: Registry) -> None:
    """Register the echo adapter in a caller-owned registry."""
    reg.register(ECHO_KIND, lambda _config: Echo())

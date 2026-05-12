"""Deterministic echo inference adapter."""

from __future__ import annotations

from pykit_ai import Model, Provider, Usage
from pykit_component import Health, HealthStatus
from pykit_inference.registry import Registry
from pykit_inference.types import InferenceDescriptor, PredictRequest, PredictResponse
from pykit_tool import Envelope

ECHO_KIND = "echo"


class Echo:
    """Lean default adapter that returns request inputs unchanged."""

    def __init__(self, *, name: str = ECHO_KIND) -> None:
        self._started = False
        self._descriptor = InferenceDescriptor(
            name=name,
            description="Echo inference adapter for tests and local wiring",
            serving_protocol="echo",
            envelope=Envelope(scopes=("inference:predict",)),
        )

    @property
    def name(self) -> str:
        """Return the component name."""
        return self._descriptor.name

    async def is_available(self) -> bool:
        """Report whether the adapter can currently serve requests."""
        return True

    async def start(self) -> None:
        """Mark the echo adapter ready."""
        self._started = True

    async def stop(self) -> None:
        """Mark the echo adapter stopped."""
        self._started = False

    async def health(self) -> Health:
        """Return the echo adapter lifecycle health."""
        status = HealthStatus.HEALTHY if self._started else HealthStatus.UNHEALTHY
        message = "ready" if self._started else "not started"
        return Health(name=self.name, status=status, message=message)

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

    async def execute(self, input: PredictRequest) -> PredictResponse:
        """Satisfy pykit-provider RequestResponse by forwarding to ``predict``."""
        return await self.predict(input)


def register(reg: Registry) -> None:
    """Register the echo adapter in a caller-owned registry."""
    reg.register(ECHO_KIND, lambda _config: Echo())

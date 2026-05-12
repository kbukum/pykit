"""Text Generation Inference OAI-compatible chat completions adapter."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from pykit_ai import Model, Provider
from pykit_ai.semconv import Operation
from pykit_authz import Decider
from pykit_component import Health, HealthStatus
from pykit_httpclient import HttpError
from pykit_inference._http import InferenceHttpClient, build_http_client, map_http_error
from pykit_inference._runtime import (
    ExecutePolicy,
    authorize_prediction,
    execute_with_policy,
    trace_prediction,
)
from pykit_inference.errors import InferenceError
from pykit_inference.types import (
    InferenceDescriptor,
    PredictRequest,
    PredictResponse,
    PredictStatus,
    Usage,
    Value,
    ValueKind,
)
from pykit_tool import Envelope, NetworkPolicy, NetworkRule


class TGIConfig(BaseModel):
    """Configuration for the TGI OAI-compat adapter."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://localhost:8080"
    model: str = "tgi"
    max_tokens: int = 256
    timeout_seconds: float = 30.0
    name: str = "tgi"
    description: str = "Text Generation Inference via OAI-compatible /v1/chat/completions"
    network_host: str = "localhost"
    network_port: int | None = 8080
    network_scheme: str = "http"
    scopes: tuple[str, ...] = ("inference:predict",)


class TGIInference:
    """Async TGI adapter using the OAI-compatible /v1/chat/completions endpoint."""

    def __init__(
        self,
        config: TGIConfig | None = None,
        *,
        client: InferenceHttpClient | None = None,
        policy: ExecutePolicy | None = None,
        decider: Decider | None = None,
    ) -> None:
        self._config = config or TGIConfig()
        self._started = False
        self._client, self._owns_client = build_http_client(
            name=self._config.name,
            base_url=self._config.base_url.rstrip("/"),
            timeout=self._config.timeout_seconds,
            client=client,
        )
        self._policy = policy
        self._decider = decider
        self._descriptor = InferenceDescriptor(
            name=self._config.name,
            description=self._config.description,
            serving_protocol="tgi",
            envelope=Envelope(
                scopes=self._config.scopes,
                network=NetworkPolicy(
                    rules=(
                        NetworkRule(
                            host=self._config.network_host,
                            port=self._config.network_port,
                            scheme=self._config.network_scheme,
                        ),
                    )
                ),
            ),
        )

    @property
    def name(self) -> str:
        """Return the component name."""
        return self._descriptor.name

    async def is_available(self) -> bool:
        """Report whether the adapter can currently serve requests."""
        return not self._client.is_closed

    async def start(self) -> None:
        """Mark the adapter ready for inference requests."""
        self._started = True

    async def stop(self) -> None:
        """Close owned resources and mark the adapter stopped."""
        self._started = False
        await self.close()

    async def health(self) -> Health:
        """Return TGI adapter lifecycle health."""
        if not self._started:
            return Health(name=self.name, status=HealthStatus.UNHEALTHY, message="not started")
        return Health(name=self.name, status=HealthStatus.HEALTHY, message="ready")

    def descriptor(self) -> InferenceDescriptor:
        """Return adapter descriptor and executable envelope."""
        return self._descriptor

    async def predict(self, request: PredictRequest) -> PredictResponse:
        """Execute a prediction via TGI /v1/chat/completions."""
        await authorize_prediction(self._decider, self._descriptor, request)

        async def do_call() -> PredictResponse:
            return await trace_prediction(
                system="tgi",
                operation_name=Operation.INFERENCE_REQUEST,
                request=request,
                call=lambda: self._predict_once(request),
            )

        return await execute_with_policy(self._policy, do_call)

    async def execute(self, input: PredictRequest) -> PredictResponse:
        """Satisfy pykit-provider RequestResponse by forwarding to ``predict``."""
        return await self.predict(input)

    async def close(self) -> None:
        """Close the owned HTTP client."""
        if self._owns_client:
            await self._client.close()

    async def _predict_once(self, request: PredictRequest) -> PredictResponse:
        prompt = _extract_prompt(request)
        model = request.model_name or self._config.model
        raw_max = request.parameters.get("max_tokens", self._config.max_tokens)
        max_tokens = int(raw_max) if isinstance(raw_max, (int, float, str)) else self._config.max_tokens
        raw_temp = request.parameters.get("temperature")

        body: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "stream": False,
        }
        if isinstance(raw_temp, (int, float, str)):
            body["temperature"] = float(raw_temp)

        try:
            response = await self._client.post("/v1/chat/completions", body=body)
        except HttpError as exc:
            raise map_http_error(exc) from exc

        data = response.json()
        if not isinstance(data, dict):
            raise InferenceError("TGI response body must be a JSON object")

        choices = data.get("choices", [])
        generated = ""
        finish_reason = None
        if choices:
            message = choices[0].get("message", {})
            generated = message.get("content", "") or ""
            finish_reason = choices[0].get("finish_reason")

        usage_raw = data.get("usage", {})
        usage = Usage(
            input_tokens=int(usage_raw.get("prompt_tokens", 0)),
            output_tokens=int(usage_raw.get("completion_tokens", 0)),
        )

        metadata: dict[str, str] = {}
        if finish_reason:
            metadata["finish_reason"] = finish_reason

        return PredictResponse(
            outputs={"text": Value(kind=ValueKind.TEXT, text=generated)},
            usage=usage,
            metadata=metadata,
            model=Model(name=data.get("model", model), provider=Provider.TGI),
            status=PredictStatus.SUCCESS,
        )


def _extract_prompt(request: PredictRequest) -> str:
    for key in ("prompt", "text"):
        val = request.inputs.get(key)
        if val is not None and val.kind == ValueKind.TEXT and val.text is not None:
            return val.text
    return ""

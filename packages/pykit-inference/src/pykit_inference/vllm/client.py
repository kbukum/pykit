"""vLLM OAI-compatible text completions adapter."""

from __future__ import annotations

from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from pykit_ai import Model, Provider
from pykit_ai.semconv import Operation
from pykit_authz import Decider
from pykit_inference._runtime import (
    ExecutePolicy,
    authorize_prediction,
    execute_with_policy,
    trace_prediction,
)
from pykit_inference.errors import InferenceError, InferenceHTTPError
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


class VLLMConfig(BaseModel):
    """Configuration for the vLLM OAI-compat adapter."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://localhost:8000"
    model: str = "default"
    max_tokens: int = 256
    timeout_seconds: float = 30.0
    name: str = "vllm"
    description: str = "vLLM text generation via OAI-compatible /v1/completions"
    network_host: str = "localhost"
    network_port: int | None = 8000
    network_scheme: str = "http"
    scopes: tuple[str, ...] = ("inference:predict",)


class VLLMInference:
    """Async vLLM adapter using the OAI-compatible /v1/completions endpoint."""

    def __init__(
        self,
        config: VLLMConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        policy: ExecutePolicy | None = None,
        decider: Decider | None = None,
    ) -> None:
        self._config = config or VLLMConfig()
        if client is not None:
            self._client = client
            self._owns_client = False
        else:
            self._client = httpx.AsyncClient(base_url=self._config.base_url.rstrip("/"))
            self._owns_client = True
        self._policy = policy
        self._decider = decider
        self._descriptor = InferenceDescriptor(
            name=self._config.name,
            description=self._config.description,
            serving_protocol="vllm",
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

    def descriptor(self) -> InferenceDescriptor:
        """Return adapter descriptor and executable envelope."""
        return self._descriptor

    async def predict(self, request: PredictRequest) -> PredictResponse:
        """Execute a prediction via vLLM /v1/completions."""
        await authorize_prediction(self._decider, self._descriptor, request)

        async def do_call() -> PredictResponse:
            return await trace_prediction(
                system="vllm",
                operation_name=Operation.INFERENCE_REQUEST,
                request=request,
                call=lambda: self._predict_once(request),
            )

        return await execute_with_policy(self._policy, do_call)

    async def close(self) -> None:
        """Close the owned HTTP client."""
        if self._owns_client:
            await self._client.aclose()

    async def _predict_once(self, request: PredictRequest) -> PredictResponse:
        prompt = _extract_prompt(request)
        model = request.model_name or self._config.model
        raw_max = request.parameters.get("max_tokens", self._config.max_tokens)
        max_tokens = int(raw_max) if isinstance(raw_max, (int, float, str)) else self._config.max_tokens
        raw_temp = request.parameters.get("temperature")

        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if isinstance(raw_temp, (int, float, str)):
            body["temperature"] = float(raw_temp)

        response = await self._client.post(
            "/v1/completions",
            json=body,
            timeout=self._config.timeout_seconds,
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise InferenceHTTPError(response.status_code, response.text)

        data = response.json()
        if not isinstance(data, dict):
            raise InferenceError("vLLM response body must be a JSON object")

        choices = data.get("choices", [])
        generated = choices[0].get("text", "") if choices else ""
        finish_reason = choices[0].get("finish_reason") if choices else None

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
            model=Model(name=data.get("model", model), provider=Provider.VLLM),
            status=PredictStatus.SUCCESS,
        )


def _extract_prompt(request: PredictRequest) -> str:
    for key in ("prompt", "text"):
        val = request.inputs.get(key)
        if val is not None and val.kind == ValueKind.TEXT and val.text is not None:
            return val.text
    return ""

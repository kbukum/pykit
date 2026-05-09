"""Triton KServe v2 HTTP inference adapter."""

from __future__ import annotations

import base64
import json
import secrets
import time
import uuid
from collections.abc import Mapping
from typing import cast

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
    Tensor,
    Usage,
    Value,
    ValueKind,
)
from pykit_tool import Envelope, NetworkPolicy, NetworkRule

_SUPPORTED_DTYPES = {"FP32", "INT64", "BYTES"}


class TritonConfig(BaseModel):
    """Configuration for Triton KServe v2 HTTP serving."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = "http://localhost:8000"
    timeout_seconds: float = 30.0
    name: str = "triton"
    description: str = "Triton KServe v2 model-serving adapter"
    network_host: str = "localhost"
    network_port: int | None = 8000
    network_scheme: str = "http"
    scopes: tuple[str, ...] = ("inference:predict",)


class TritonInference:
    """Async Triton KServe v2 HTTP adapter."""

    def __init__(
        self,
        config: TritonConfig | None = None,
        *,
        client: httpx.AsyncClient | None = None,
        policy: ExecutePolicy | None = None,
        decider: Decider | None = None,
    ) -> None:
        self._config = config or TritonConfig()
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
            serving_protocol="kserve-v2",
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
        """Execute ``/v2/models/{name}/infer`` using the KServe v2 protocol."""
        if request.request_id is None:
            request = request.model_copy(update={"request_id": _uuid7()})
        await authorize_prediction(self._decider, self._descriptor, request)

        async def do_call() -> PredictResponse:
            return await trace_prediction(
                system="triton",
                operation_name=Operation.INFERENCE_REQUEST,
                request=request,
                call=lambda: self._predict_once(request),
            )

        return await execute_with_policy(self._policy, do_call)

    async def health_check(self) -> bool:
        """Return whether Triton reports ``/v2/health/ready`` successfully."""
        response = await self._client.get("/v2/health/ready", timeout=self._config.timeout_seconds)
        return 200 <= response.status_code < 300

    async def close(self) -> None:
        """Close the owned HTTP client."""
        if self._owns_client:
            await self._client.aclose()

    async def _predict_once(self, request: PredictRequest) -> PredictResponse:
        path = _infer_path(request.model_name, request.model_version)
        response = await self._client.post(
            path,
            json=_encode_request(request),
            timeout=self._config.timeout_seconds,
        )
        if response.status_code < 200 or response.status_code >= 300:
            raise InferenceHTTPError(response.status_code, response.text)
        body = response.json()
        if not isinstance(body, dict):
            raise InferenceError("Triton response body must be a JSON object")
        return _decode_response(cast("dict[str, object]", body), request)


def _infer_path(model_name: str, model_version: str | None) -> str:
    escaped_model = _path_segment(model_name)
    if model_version is None:
        return f"/v2/models/{escaped_model}/infer"
    return f"/v2/models/{escaped_model}/versions/{_path_segment(model_version)}/infer"


def _path_segment(value: str) -> str:
    if "/" in value or not value:
        raise ValueError("model path segments must be non-empty and cannot contain '/'")
    return value


def _encode_request(request: PredictRequest) -> dict[str, object]:
    payload: dict[str, object] = {
        "inputs": [_encode_input(name, value) for name, value in request.inputs.items()],
    }
    if request.request_id is not None:
        payload["id"] = request.request_id
    if request.parameters or request.options:
        payload["parameters"] = {**request.parameters, **request.options}
    return payload


def _encode_input(name: str, value: Value) -> dict[str, object]:
    match value.kind:
        case ValueKind.TEXT:
            if value.text is None:
                raise ValueError(f"text input {name!r} is missing text")
            return {"name": name, "shape": [1], "datatype": "BYTES", "data": [value.text]}
        case ValueKind.BYTES:
            if value.bytes_ is None:
                raise ValueError(f"bytes input {name!r} is missing bytes")
            return {
                "name": name,
                "shape": [1],
                "datatype": "BYTES",
                "data": [base64.b64encode(value.bytes_).decode("ascii")],
                "parameters": {"content_encoding": "base64"},
            }
        case ValueKind.TENSOR:
            if value.tensor is None:
                raise ValueError(f"tensor input {name!r} is missing tensor")
            return _encode_tensor(name, value.tensor)
        case ValueKind.JSON:
            if value.json_ is None:
                raise ValueError(f"json input {name!r} is missing json")
            return {
                "name": name,
                "shape": [1],
                "datatype": "BYTES",
                "data": [json.dumps(value.json_, separators=(",", ":"))],
                "parameters": {"content_type": "application/json"},
            }
        case _:
            raise ValueError(f"unsupported Triton input kind for {name!r}: {value.kind!r}")


def _encode_tensor(name: str, tensor: Tensor) -> dict[str, object]:
    dtype = tensor.dtype.upper()
    if dtype not in _SUPPORTED_DTYPES:
        raise ValueError(f"unsupported Triton tensor dtype {tensor.dtype!r}")
    data: list[float] | list[int] | list[str]
    parameters: dict[str, object] = {}
    if dtype == "BYTES":
        if not isinstance(tensor.data, bytes):
            raise ValueError("BYTES tensor data must be bytes")
        data = [base64.b64encode(tensor.data).decode("ascii")]
        parameters["content_encoding"] = "base64"
    elif dtype == "FP32":
        if not isinstance(tensor.data, list):
            raise ValueError("FP32 tensor data must be a float list")
        data = [float(item) for item in tensor.data]
    else:
        if not isinstance(tensor.data, list):
            raise ValueError("INT64 tensor data must be an integer list")
        data = [int(item) for item in tensor.data]
    encoded: dict[str, object] = {"name": name, "shape": tensor.shape, "datatype": dtype, "data": data}
    if parameters:
        encoded["parameters"] = parameters
    return encoded


def _decode_response(body: Mapping[str, object], request: PredictRequest) -> PredictResponse:
    raw_outputs = body.get("outputs", [])
    if not isinstance(raw_outputs, list):
        raise InferenceError("Triton response outputs must be a list")
    outputs: dict[str, Value] = {}
    for raw in raw_outputs:
        if not isinstance(raw, dict):
            raise InferenceError("Triton output entry must be an object")
        name, value = _decode_output(cast("dict[str, object]", raw))
        outputs[name] = value

    metadata: dict[str, str] = {}
    response_id = body.get("id")
    if isinstance(response_id, str):
        metadata["id"] = response_id
    model_name = body.get("model_name")
    served_model = model_name if isinstance(model_name, str) else request.model_name
    model_version = body.get("model_version")
    served_version = model_version if isinstance(model_version, str) else (request.model_version or "")

    usage = _decode_usage(body.get("parameters"))
    return PredictResponse(
        outputs=outputs,
        usage=usage,
        metadata=metadata,
        model=Model(name=served_model, provider=Provider.TRITON, version=served_version),
        status=PredictStatus.SUCCESS,
    )


def _decode_output(raw: dict[str, object]) -> tuple[str, Value]:
    name = raw.get("name")
    dtype = raw.get("datatype", raw.get("dtype"))
    shape = raw.get("shape", [])
    data = raw.get("data", [])
    if not isinstance(name, str) or not name:
        raise InferenceError("Triton output name is required")
    if not isinstance(dtype, str):
        raise InferenceError(f"Triton output {name!r} datatype is required")
    if not isinstance(shape, list) or not all(isinstance(item, int) for item in shape):
        raise InferenceError(f"Triton output {name!r} shape must be an integer list")

    normalized_dtype = dtype.upper()
    tensor_data: list[float] | list[int] | bytes
    if normalized_dtype == "FP32":
        tensor_data = _numeric_list(data, float)
    elif normalized_dtype == "INT64":
        tensor_data = _numeric_list(data, int)
    elif normalized_dtype == "BYTES":
        tensor_data = _decode_bytes_data(data, raw.get("parameters"))
    else:
        raise InferenceError(f"unsupported Triton response dtype {dtype!r}")

    return name, Value(
        kind=ValueKind.TENSOR, tensor=Tensor(dtype=normalized_dtype, shape=shape, data=tensor_data)
    )


def _numeric_list[Number: (int, float)](raw: object, caster: type[Number]) -> list[Number]:
    if not isinstance(raw, list):
        raise InferenceError("numeric tensor data must be a list")
    values: list[Number] = []
    for item in raw:
        if not isinstance(item, (int, float)):
            raise InferenceError("numeric tensor data contains a non-number")
        values.append(caster(item))
    return values


def _decode_bytes_data(raw: object, parameters: object) -> bytes:
    if isinstance(raw, str):
        candidate = raw
    elif isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], str):
        candidate = raw[0]
    elif isinstance(raw, list) and all(isinstance(item, str) for item in raw):
        return b"".join(item.encode() for item in raw)
    else:
        raise InferenceError("BYTES tensor data must be a string or list of strings")

    if _is_base64(parameters):
        return base64.b64decode(candidate.encode("ascii"), validate=True)
    return candidate.encode()


def _is_base64(parameters: object) -> bool:
    return isinstance(parameters, dict) and parameters.get("content_encoding") == "base64"


def _decode_usage(raw_parameters: object) -> Usage:
    if not isinstance(raw_parameters, dict):
        return Usage()
    return Usage(
        input_tokens=_int_parameter(raw_parameters, "input_tokens"),
        output_tokens=_int_parameter(raw_parameters, "output_tokens"),
        cached_tokens=_int_parameter(raw_parameters, "cached_tokens"),
        reasoning_tokens=_int_parameter(raw_parameters, "reasoning_tokens"),
    )


def _int_parameter(parameters: Mapping[object, object], key: str) -> int:
    value = parameters.get(key, 0)
    if isinstance(value, int):
        return value
    return 0


def _uuid7() -> str:
    millis = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = (millis << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return str(uuid.UUID(int=value))

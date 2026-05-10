"""Triton KServe v2 adapter tests."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_authz import Decision, DecisionRequest
from pykit_httpclient import HttpClient, HttpConfig
from pykit_inference import PredictRequest, PredictStatus, Tensor, Value, ValueKind
from pykit_inference.errors import InferenceAuthorizationError, InferenceHTTPError
from pykit_inference.registry import Registry
from pykit_inference.triton import register
from pykit_inference.triton.client import TritonConfig, TritonInference
from pykit_inference.triton.register import TRITON_KIND


class AllowDecider:
    async def decide(self, request: DecisionRequest) -> Decision:
        return Decision(allowed=True, reason=request.action)


class DenyDecider:
    async def decide(self, request: DecisionRequest) -> Decision:
        return Decision(allowed=False, reason="no")


async def test_triton_predict_happy_path() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/models/classifier/versions/v2/infer"
        payload = json.loads(request.content.decode())
        assert payload["id"] == "req-1"
        assert payload["inputs"] == [
            {"name": "features", "shape": [1, 2], "datatype": "FP32", "data": [0.25, 0.75]}
        ]
        return httpx.Response(
            200,
            json={
                "id": "req-1",
                "model_name": "classifier",
                "model_version": "v2",
                "outputs": [
                    {"name": "scores", "shape": [1, 2], "datatype": "FP32", "data": [0.1, 0.9]},
                    {
                        "name": "label_bytes",
                        "shape": [1],
                        "datatype": "BYTES",
                        "data": ["bGFiZWw="],
                        "parameters": {"content_encoding": "base64"},
                    },
                ],
                "parameters": {
                    "input_tokens": 3,
                    "output_tokens": 5,
                    "cached_tokens": 1,
                    "reasoning_tokens": 7,
                },
            },
        )

    client = HttpClient(HttpConfig(base_url="http://triton.test"), transport=httpx.MockTransport(handler))
    adapter = TritonInference(
        TritonConfig(base_url="http://triton.test"), client=client, decider=AllowDecider()
    )

    response = await adapter.predict(
        PredictRequest(
            model_name="classifier",
            model_version="v2",
            request_id="req-1",
            inputs={
                "features": Value(
                    kind=ValueKind.TENSOR,
                    tensor=Tensor(dtype="FP32", shape=[1, 2], data=[0.25, 0.75]),
                )
            },
        )
    )

    assert response.outputs["scores"].tensor == Tensor(dtype="FP32", shape=[1, 2], data=[0.1, 0.9])
    assert response.outputs["label_bytes"].tensor == Tensor(dtype="BYTES", shape=[1], data=b"label")
    assert response.usage.input_tokens == 3
    assert response.usage.output_tokens == 5
    assert response.usage.cached_tokens == 1
    assert response.usage.reasoning_tokens == 7
    assert response.model.name == "classifier"
    assert response.model.version == "v2"
    assert response.status is PredictStatus.SUCCESS
    await client.close()


async def test_triton_predict_error_response() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="not ready")

    client = HttpClient(HttpConfig(base_url="http://triton.test"), transport=httpx.MockTransport(handler))
    adapter = TritonInference(TritonConfig(base_url="http://triton.test"), client=client)

    with pytest.raises(InferenceHTTPError, match="HTTP 503"):
        await adapter.predict(PredictRequest(model_name="classifier"))
    await client.close()


async def test_triton_generates_request_id() -> None:
    seen: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode())
        seen["id"] = payload["id"]
        return httpx.Response(200, json={"model_name": "classifier", "outputs": []})

    client = HttpClient(HttpConfig(base_url="http://triton.test"), transport=httpx.MockTransport(handler))
    adapter = TritonInference(TritonConfig(base_url="http://triton.test"), client=client)

    await adapter.predict(PredictRequest(model_name="classifier"))

    assert seen["id"]
    assert len(seen["id"].split("-")) == 5
    await client.close()


async def test_triton_health_probe() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/health/ready"
        return httpx.Response(200)

    client = HttpClient(HttpConfig(base_url="http://triton.test"), transport=httpx.MockTransport(handler))
    adapter = TritonInference(TritonConfig(base_url="http://triton.test"), client=client)

    assert await adapter.health_check() is True
    await client.close()


async def test_triton_denied_by_decider() -> None:
    client = httpx.AsyncClient(
        base_url="http://triton.test", transport=httpx.MockTransport(lambda _r: httpx.Response(200))
    )
    adapter = TritonInference(
        TritonConfig(base_url="http://triton.test"), client=client, decider=DenyDecider()
    )

    with pytest.raises(InferenceAuthorizationError, match="no"):
        await adapter.predict(PredictRequest(model_name="classifier"))
    await client.aclose()


@pytest.mark.asyncio
async def test_triton_register_factory() -> None:
    registry = Registry()
    register(registry)

    built = registry.build(TRITON_KIND, {"base_url": "http://triton.test"})

    assert isinstance(built, TritonInference)
    await built.close()


@pytest.mark.asyncio
async def test_triton_close_only_closes_injected_canonical_client() -> None:
    injected = HttpClient(HttpConfig(base_url="http://triton.test"))
    adapter = TritonInference(TritonConfig(base_url="http://triton.test"), client=injected)

    await adapter.close()

    assert injected.is_closed is False
    await injected.close()


@pytest.mark.asyncio
async def test_triton_accepts_raw_async_client_for_backward_compatibility() -> None:
    injected = httpx.AsyncClient(base_url="http://triton.test")
    adapter = TritonInference(TritonConfig(base_url="http://triton.test"), client=injected)

    await adapter.close()

    assert injected.is_closed is False
    await injected.aclose()


@pytest.mark.asyncio
async def test_triton_close_closes_default_client() -> None:
    adapter = TritonInference(TritonConfig(base_url="http://triton.test"))

    await adapter.close()

    assert adapter._client.is_closed is True

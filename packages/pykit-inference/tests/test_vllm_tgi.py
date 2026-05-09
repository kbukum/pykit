"""vLLM and TGI OAI-compatible adapter tests."""

from __future__ import annotations

import json

import httpx
import pytest

from pykit_authz import Decision, DecisionRequest
from pykit_inference import PredictRequest, PredictStatus, Value, ValueKind
from pykit_inference.errors import InferenceAuthorizationError, InferenceHTTPError
from pykit_inference.registry import Registry
from pykit_inference.tgi import register as tgi_register
from pykit_inference.tgi.client import TGIConfig, TGIInference
from pykit_inference.tgi.register import TGI_KIND
from pykit_inference.vllm import register as vllm_register
from pykit_inference.vllm.client import VLLMConfig, VLLMInference
from pykit_inference.vllm.register import VLLM_KIND


class AllowDecider:
    async def decide(self, request: DecisionRequest) -> Decision:
        return Decision(allowed=True, reason=request.action)


class DenyDecider:
    async def decide(self, request: DecisionRequest) -> Decision:
        return Decision(allowed=False, reason="denied")


# ─────────────────────────── vLLM ────────────────────────────────────────────


async def test_vllm_predict_happy_path() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/completions"
        payload = json.loads(request.content.decode())
        assert payload["prompt"] == "Hello!"
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={
                "id": "cmpl-1",
                "model": "llama3",
                "choices": [{"text": "Hi there!", "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 2, "completion_tokens": 3},
            },
        )

    client = httpx.AsyncClient(base_url="http://vllm.test", transport=httpx.MockTransport(handler))
    adapter = VLLMInference(VLLMConfig(base_url="http://vllm.test", model="llama3"), client=client)

    response = await adapter.predict(
        PredictRequest(
            model_name="llama3",
            inputs={"prompt": Value(kind=ValueKind.TEXT, text="Hello!")},
        )
    )

    assert response.outputs["text"].text == "Hi there!"
    assert response.usage.input_tokens == 2
    assert response.usage.output_tokens == 3
    assert response.model.name == "llama3"
    assert response.metadata.get("finish_reason") == "stop"
    assert response.status is PredictStatus.SUCCESS
    await client.aclose()


async def test_vllm_predict_http_error() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="service unavailable")

    client = httpx.AsyncClient(base_url="http://vllm.test", transport=httpx.MockTransport(handler))
    adapter = VLLMInference(VLLMConfig(base_url="http://vllm.test"), client=client)

    with pytest.raises(InferenceHTTPError, match="HTTP 503"):
        await adapter.predict(PredictRequest(model_name="llama3"))
    await client.aclose()


async def test_vllm_denied_by_decider() -> None:
    client = httpx.AsyncClient(
        base_url="http://vllm.test", transport=httpx.MockTransport(lambda _r: httpx.Response(200))
    )
    adapter = VLLMInference(VLLMConfig(base_url="http://vllm.test"), client=client, decider=DenyDecider())

    with pytest.raises(InferenceAuthorizationError, match="denied"):
        await adapter.predict(PredictRequest(model_name="llama3"))
    await client.aclose()


@pytest.mark.asyncio
async def test_vllm_register_factory() -> None:
    registry = Registry()
    vllm_register(registry)

    built = registry.build(VLLM_KIND, {"base_url": "http://vllm.test"})

    assert isinstance(built, VLLMInference)
    await built.close()


def test_vllm_descriptor() -> None:
    client = httpx.AsyncClient(base_url="http://vllm.test")
    adapter = VLLMInference(VLLMConfig(base_url="http://vllm.test"), client=client)
    descriptor = adapter.descriptor()

    assert descriptor.serving_protocol == "vllm"
    assert descriptor.envelope.scopes == ("inference:predict",)
    assert client.is_closed is False


@pytest.mark.asyncio
async def test_vllm_close_only_closes_owned_client() -> None:
    injected = httpx.AsyncClient(base_url="http://vllm.test")
    adapter = VLLMInference(VLLMConfig(base_url="http://vllm.test"), client=injected)

    await adapter.close()

    assert injected.is_closed is False
    await injected.aclose()


@pytest.mark.asyncio
async def test_vllm_close_closes_default_client() -> None:
    adapter = VLLMInference(VLLMConfig(base_url="http://vllm.test"))

    await adapter.close()

    assert adapter._client.is_closed is True


# ─────────────────────────── TGI ─────────────────────────────────────────────


async def test_tgi_predict_happy_path() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        payload = json.loads(request.content.decode())
        assert payload["messages"] == [{"role": "user", "content": "Hello!"}]
        assert payload["stream"] is False
        return httpx.Response(
            200,
            json={
                "id": "chat-1",
                "model": "mistral-7b",
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "Hi from TGI!"},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 3, "completion_tokens": 4},
            },
        )

    client = httpx.AsyncClient(base_url="http://tgi.test", transport=httpx.MockTransport(handler))
    adapter = TGIInference(TGIConfig(base_url="http://tgi.test", model="mistral-7b"), client=client)

    response = await adapter.predict(
        PredictRequest(
            model_name="mistral-7b",
            inputs={"prompt": Value(kind=ValueKind.TEXT, text="Hello!")},
        )
    )

    assert response.outputs["text"].text == "Hi from TGI!"
    assert response.usage.input_tokens == 3
    assert response.usage.output_tokens == 4
    assert response.model.name == "mistral-7b"
    assert response.metadata.get("finish_reason") == "stop"
    assert response.status is PredictStatus.SUCCESS
    await client.aclose()


async def test_tgi_predict_http_error() -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(502, text="bad gateway")

    client = httpx.AsyncClient(base_url="http://tgi.test", transport=httpx.MockTransport(handler))
    adapter = TGIInference(TGIConfig(base_url="http://tgi.test"), client=client)

    with pytest.raises(InferenceHTTPError, match="HTTP 502"):
        await adapter.predict(PredictRequest(model_name="mistral-7b"))
    await client.aclose()


async def test_tgi_denied_by_decider() -> None:
    client = httpx.AsyncClient(
        base_url="http://tgi.test", transport=httpx.MockTransport(lambda _r: httpx.Response(200))
    )
    adapter = TGIInference(TGIConfig(base_url="http://tgi.test"), client=client, decider=DenyDecider())

    with pytest.raises(InferenceAuthorizationError, match="denied"):
        await adapter.predict(PredictRequest(model_name="mistral-7b"))
    await client.aclose()


@pytest.mark.asyncio
async def test_tgi_register_factory() -> None:
    registry = Registry()
    tgi_register(registry)

    built = registry.build(TGI_KIND, {"base_url": "http://tgi.test"})

    assert isinstance(built, TGIInference)
    await built.close()


def test_tgi_descriptor() -> None:
    client = httpx.AsyncClient(base_url="http://tgi.test")
    adapter = TGIInference(TGIConfig(base_url="http://tgi.test"), client=client)
    descriptor = adapter.descriptor()

    assert descriptor.serving_protocol == "tgi"
    assert descriptor.envelope.scopes == ("inference:predict",)
    assert client.is_closed is False


@pytest.mark.asyncio
async def test_tgi_close_only_closes_owned_client() -> None:
    injected = httpx.AsyncClient(base_url="http://tgi.test")
    adapter = TGIInference(TGIConfig(base_url="http://tgi.test"), client=injected)

    await adapter.close()

    assert injected.is_closed is False
    await injected.aclose()


@pytest.mark.asyncio
async def test_tgi_close_closes_default_client() -> None:
    adapter = TGIInference(TGIConfig(base_url="http://tgi.test"))

    await adapter.close()

    assert adapter._client.is_closed is True

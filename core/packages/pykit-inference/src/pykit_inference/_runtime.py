"""Shared runtime integration helpers for inference adapters."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

from pykit_ai.semconv import (
    GENAI_OPERATION_NAME,
    GENAI_REQUEST_ID,
    GENAI_REQUEST_MAX_TOKENS,
    GENAI_REQUEST_MODEL,
    GENAI_REQUEST_MODEL_VERSION,
    GENAI_RESPONSE_FINISH_REASON,
    GENAI_RESPONSE_MODEL,
    GENAI_SYSTEM,
    GENAI_USAGE_CACHED_TOKENS,
    GENAI_USAGE_INPUT_TOKENS,
    GENAI_USAGE_OUTPUT_TOKENS,
    GENAI_USAGE_REASONING_TOKENS,
    Operation,
)
from pykit_authz import Decider, DecisionRequest
from pykit_inference.errors import InferenceAuthorizationError
from pykit_inference.types import InferenceDescriptor, PredictRequest, PredictResponse
from pykit_observability import SpanKind, start_span


class ExecutePolicy(Protocol):
    """Subset of pykit_resilience.Policy consumed by adapters."""

    async def execute[T](self, fn: Callable[[], Awaitable[T]]) -> T:
        """Execute an async callable within the configured policy."""


async def authorize_prediction(
    decider: Decider | None, descriptor: InferenceDescriptor, request: PredictRequest
) -> None:
    """Authorize a prediction when a decider is injected; default is open."""
    if decider is None:
        return
    decision = await decider.decide(
        DecisionRequest(
            principal=request.metadata.get("principal", "anonymous"),
            action="inference:predict",
            resource=f"inference:{descriptor.name}:{request.model_name}",
            scopes=descriptor.envelope.scopes,
            context={
                "model_name": request.model_name,
                "model_version": request.model_version or "",
                "serving_protocol": descriptor.serving_protocol,
            },
        )
    )
    if not decision.allowed:
        reason = decision.reason or "denied"
        raise InferenceAuthorizationError(reason)


async def execute_with_policy[T](policy: ExecutePolicy | None, fn: Callable[[], Awaitable[T]]) -> T:
    """Execute through injected resilience policy when present."""
    if policy is None:
        return await fn()
    return await policy.execute(fn)


async def trace_prediction(
    *,
    system: str,
    operation_name: Operation = Operation.INFERENCE_REQUEST,
    request: PredictRequest,
    call: Callable[[], Awaitable[PredictResponse]],
) -> PredictResponse:
    """Emit an OTel GenAI span around a prediction call."""
    attributes: dict[str, str | int | float | bool] = {
        GENAI_SYSTEM: system,
        GENAI_OPERATION_NAME: operation_name.value,
        GENAI_REQUEST_MODEL: request.model_name,
    }
    if request.model_version is not None:
        attributes[GENAI_REQUEST_MODEL_VERSION] = request.model_version
    if request.request_id is not None:
        attributes[GENAI_REQUEST_ID] = request.request_id
    max_tokens = request.parameters.get("max_tokens")
    if isinstance(max_tokens, (int, float)) and not isinstance(max_tokens, bool):
        attributes[GENAI_REQUEST_MAX_TOKENS] = max_tokens

    with start_span(
        "pykit_inference",
        f"inference.{system}.{operation_name.value}",
        kind=SpanKind.CLIENT,
        attributes=attributes,
    ) as span:
        try:
            response = await call()
        except Exception as exc:
            span.record_exception(exc)
            span.set_error(str(exc))
            raise
        span.set_attribute(GENAI_USAGE_INPUT_TOKENS, response.usage.input_tokens)
        span.set_attribute(GENAI_USAGE_OUTPUT_TOKENS, response.usage.output_tokens)
        span.set_attribute(GENAI_USAGE_CACHED_TOKENS, response.usage.cached_tokens)
        span.set_attribute(GENAI_USAGE_REASONING_TOKENS, response.usage.reasoning_tokens)
        if response.model.name:
            span.set_attribute(GENAI_RESPONSE_MODEL, response.model.name)
        finish_reason = response.metadata.get("finish_reason")
        if finish_reason is not None:
            span.set_attribute(GENAI_RESPONSE_FINISH_REASON, finish_reason)
        return response

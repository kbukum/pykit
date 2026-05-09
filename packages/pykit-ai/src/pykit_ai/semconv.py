"""OpenTelemetry GenAI semantic-convention attribute and operation names."""

from __future__ import annotations

from enum import StrEnum


class Operation(StrEnum):
    """Canonical values for ``gen_ai.operation.name``."""

    CHAT = "chat"
    TEXT_COMPLETION = "text_completion"
    EMBEDDING = "embedding"
    AGENT_TURN = "agent.turn"
    LLM_CALL = "llm.call"
    TOOL_CALL = "tool.call"
    MCP_REQUEST = "mcp.request"
    STREAM = "stream"
    INFERENCE_REQUEST = "inference.request"


GENAI_OPERATION_NAME = "gen_ai.operation.name"
GENAI_OPERATION_CHAT = Operation.CHAT.value
GENAI_OPERATION_TEXT_COMPLETION = Operation.TEXT_COMPLETION.value
GENAI_OPERATION_EMBEDDING = Operation.EMBEDDING.value
GENAI_OPERATION_AGENT_TURN = Operation.AGENT_TURN.value
GENAI_OPERATION_LLM_CALL = Operation.LLM_CALL.value
GENAI_OPERATION_TOOL_CALL = Operation.TOOL_CALL.value
GENAI_OPERATION_MCP_REQUEST = Operation.MCP_REQUEST.value
GENAI_OPERATION_STREAM = Operation.STREAM.value
GENAI_OPERATION_INFERENCE = Operation.INFERENCE_REQUEST.value
GENAI_SYSTEM = "gen_ai.system"
GENAI_REQUEST_ID = "gen_ai.request.id"
GENAI_REQUEST_MODEL = "gen_ai.request.model"
GENAI_REQUEST_MODEL_VERSION = "gen_ai.request.model.version"
GENAI_REQUEST_MAX_TOKENS = "gen_ai.request.max_tokens"
GENAI_REQUEST_TEMPERATURE = "gen_ai.request.temperature"
GENAI_RESPONSE_MODEL = "gen_ai.response.model"
GENAI_RESPONSE_FINISH_REASON = "gen_ai.response.finish_reason"
GENAI_TOOL_NAME = "gen_ai.tool.name"
GENAI_USAGE_INPUT_TOKENS = "gen_ai.usage.input_tokens"
GENAI_USAGE_OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
GENAI_USAGE_CACHED_TOKENS = "gen_ai.usage.cached_tokens"
GENAI_USAGE_REASONING_TOKENS = "gen_ai.usage.reasoning_tokens"

__all__ = [
    "GENAI_OPERATION_AGENT_TURN",
    "GENAI_OPERATION_CHAT",
    "GENAI_OPERATION_EMBEDDING",
    "GENAI_OPERATION_INFERENCE",
    "GENAI_OPERATION_LLM_CALL",
    "GENAI_OPERATION_MCP_REQUEST",
    "GENAI_OPERATION_NAME",
    "GENAI_OPERATION_STREAM",
    "GENAI_OPERATION_TEXT_COMPLETION",
    "GENAI_OPERATION_TOOL_CALL",
    "GENAI_REQUEST_ID",
    "GENAI_REQUEST_MAX_TOKENS",
    "GENAI_REQUEST_MODEL",
    "GENAI_REQUEST_MODEL_VERSION",
    "GENAI_REQUEST_TEMPERATURE",
    "GENAI_RESPONSE_FINISH_REASON",
    "GENAI_RESPONSE_MODEL",
    "GENAI_SYSTEM",
    "GENAI_TOOL_NAME",
    "GENAI_USAGE_CACHED_TOKENS",
    "GENAI_USAGE_INPUT_TOKENS",
    "GENAI_USAGE_OUTPUT_TOKENS",
    "GENAI_USAGE_REASONING_TOKENS",
    "Operation",
]

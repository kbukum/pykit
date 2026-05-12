"""Canonical AI model, usage, and finish metadata."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Role(StrEnum):
    """Canonical message roles."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class Provider(StrEnum):
    """Well-known model providers."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    COHERE = "cohere"
    MISTRAL = "mistral"
    META = "meta"
    AWS_BEDROCK = "aws_bedrock"
    AZURE_OPENAI = "azure_openai"
    OLLAMA = "ollama"
    TRITON = "triton"
    VLLM = "vllm"
    TGI = "tgi"
    CUSTOM = "custom"


class Capabilities(BaseModel):
    """Typed model/provider capabilities."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    streaming: bool = False
    vision: bool = False
    audio: bool = False
    tool_use: bool = False
    json_mode: bool = False
    reasoning_tokens: bool = False
    max_input_tokens: int = 0
    max_output_tokens: int = 0


class Model(BaseModel):
    """Canonical model identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    provider: Provider | str = Provider.CUSTOM
    version: str = ""
    capabilities: Capabilities = Field(default_factory=Capabilities)


class Usage(BaseModel):
    """Token usage counters, including cache and reasoning tokens."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    reasoning_tokens: int = 0


class Cost(BaseModel):
    """Typed decimal model cost."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    input: Decimal = Decimal("0")
    output: Decimal = Decimal("0")
    cached: Decimal = Decimal("0")
    reasoning: Decimal = Decimal("0")
    currency: str = "USD"


class Budget(BaseModel):
    """Shared budget vocabulary; enforcement lives in callers."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_tokens: int | None = None
    max_calls: int | None = None
    max_cost: Cost | None = None
    wall_clock: float | None = None


class BudgetExceededReason(StrEnum):
    """Reasons an AI budget may be exceeded."""

    TOKENS = "tokens"
    CALLS = "calls"
    COST = "cost"
    WALL_CLOCK = "wall_clock"
    CANCELLED = "cancelled"


class FinishReason(StrEnum):
    """Canonical model finish reasons."""

    STOP = "stop"
    LENGTH = "length"
    TOOL_USE = "tool_use"
    CONTENT_FILTER = "content_filter"
    ERROR = "error"
    CANCELLED = "cancelled"


__all__ = [
    "Budget",
    "BudgetExceededReason",
    "Capabilities",
    "Cost",
    "FinishReason",
    "Model",
    "Provider",
    "Role",
    "Usage",
]

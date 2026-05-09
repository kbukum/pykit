"""Pydantic skill manifest models."""

from __future__ import annotations

import enum
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class Safety(enum.StrEnum):
    """Informational skill safety and effective tool safety level."""

    READ_ONLY = "read_only"
    MUTATING = "mutating"
    DESTRUCTIVE = "destructive"


class PromptReference(BaseModel):
    """Referenced prompt template identity."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(alias="name")
    version: str = Field(alias="version")


class References(BaseModel):
    """Referenced executable/non-executable registrations by name/pattern."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tools: list[str] = Field(default_factory=list, alias="tools")
    prompts: list[PromptReference] = Field(default_factory=list, alias="prompts")
    resources: list[str] = Field(default_factory=list, alias="resources")
    mcp_servers: list[str] = Field(default_factory=list, alias="mcp_servers")


class MaxCost(BaseModel):
    """Decimal currency budget."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    amount: Decimal = Field(alias="amount")
    currency: str = Field(alias="currency")


class Budgets(BaseModel):
    """Activation budget hints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_tokens: int | None = Field(default=None, alias="max_tokens")
    max_calls: int | None = Field(default=None, alias="max_calls")
    max_cost: MaxCost | None = Field(default=None, alias="max_cost")
    wall_clock: str | None = Field(default=None, alias="wall_clock")


class Requires(BaseModel):
    """Activation preconditions only; never grants executable authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scopes: list[str] = Field(default_factory=list, alias="scopes")
    capabilities: list[str] = Field(default_factory=list, alias="capabilities")


class HumanApproval(BaseModel):
    """Human approval rule for a workflow step."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    step: str = Field(alias="step")
    when: str = Field(alias="when")
    rationale: str = Field(alias="rationale")


class ModelHints(BaseModel):
    """Optional model-selection hints."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    preferred: list[str] = Field(default_factory=list, alias="preferred")
    reject: list[str] = Field(default_factory=list, alias="reject")


class ProgressiveDisclosure(BaseModel):
    """Progressive disclosure text for UIs and agents."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    summary: str = Field(alias="summary")
    detail: str = Field(alias="detail")


class Script(BaseModel):
    """Inert script asset declaration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str = Field(alias="path")
    description: str = Field(alias="description")


class Signature(BaseModel):
    """Detached manifest signature metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    algorithm: str = Field(alias="algorithm")
    value: str = Field(alias="value")
    key_id: str = Field(alias="key_id")


class Manifest(BaseModel):
    """Canonical `kit.skill.yaml` manifest."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = Field(default="1", alias="schema_version")
    name: str = Field(alias="name")
    version: str = Field(alias="version")
    description: str = Field(alias="description")
    license: str | None = Field(default=None, alias="license")
    authors: list[str] = Field(default_factory=list, alias="authors")
    references: References = Field(default_factory=References, alias="references")
    requires: Requires = Field(default_factory=Requires, alias="requires")
    human_approval: list[HumanApproval] = Field(default_factory=list, alias="human_approval")
    budgets: Budgets | None = Field(default=None, alias="budgets")
    model_hints: ModelHints | None = Field(default=None, alias="model_hints")
    progressive_disclosure: ProgressiveDisclosure | None = Field(default=None, alias="progressive_disclosure")
    scripts: list[Script] = Field(default_factory=list, alias="scripts")
    signature: Signature | None = Field(default=None, alias="signature")
    safety: Safety = Field(default=Safety.READ_ONLY, alias="safety")


class ScriptAsset(BaseModel):
    """Loaded inert script asset metadata; loaders never execute scripts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    sha256: str

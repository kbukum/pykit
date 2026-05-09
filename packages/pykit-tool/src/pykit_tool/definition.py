"""Tool definition types and executable permission envelopes."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Safety(StrEnum):
    """Executable safety level; ordered read-only < mutating < destructive."""

    READ_ONLY = "read_only"
    MUTATING = "mutating"
    DESTRUCTIVE = "destructive"


class DataClassification(StrEnum):
    """Informational data-classification tag for redaction policies."""

    PUBLIC = "public"
    PII = "pii"
    SECRET = "secret"


class FilesystemMode(StrEnum):
    """Allowed filesystem operation mode."""

    READ = "read"
    WRITE = "write"
    DELETE = "delete"


class SensitiveMatcher(StrEnum):
    """Supported sensitive-invocation predicate matcher."""

    EXISTS = "exists"
    EQUALS = "equals"
    REGEX = "regex"
    GT = "gt"
    LT = "lt"


class NetworkRule(BaseModel):
    """Default-deny network egress allow-list entry."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    host: str
    port: int | None = None
    scheme: str = "https"


class NetworkPolicy(BaseModel):
    """Network egress policy. Empty rules deny all egress."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rules: tuple[NetworkRule, ...] = ()


class FilesystemRule(BaseModel):
    """Filesystem path rule. Paths are normalized by the enforcer."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    path: str
    mode: FilesystemMode


class SubprocessRule(BaseModel):
    """Argv-only subprocess rule. Shell invocation is forbidden."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    argv_pattern: tuple[str, ...] = Field(default_factory=tuple)
    env_allow: tuple[str, ...] = Field(default_factory=tuple)
    cwd: str | None = None


class SensitivePredicate(BaseModel):
    """Predicate over validated tool input that elevates to HITL."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    jsonpath: str
    matcher: SensitiveMatcher
    value: str | int | float | bool | None = None


class Envelope(BaseModel):
    """Default-deny executable permission envelope for a tool/resource."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    scopes: tuple[str, ...] = Field(default_factory=tuple)
    network: NetworkPolicy = Field(default_factory=NetworkPolicy)
    filesystem: tuple[FilesystemRule, ...] = Field(default_factory=tuple)
    subprocess: tuple[SubprocessRule, ...] = Field(default_factory=tuple)
    safety: Safety = Safety.READ_ONLY
    sensitive_invocations: tuple[SensitivePredicate, ...] = Field(default_factory=tuple)
    data_classification: DataClassification = DataClassification.PUBLIC


class ExecutionHint(StrEnum):
    """Where a tool executes from the caller's perspective."""

    BACKEND = "backend"
    UI = "ui"
    HYBRID = "hybrid"


class Annotations(BaseModel):
    """Non-executable tool metadata. Executable authority lives in Envelope."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = ""
    category: str = ""
    tags: list[str] = Field(default_factory=list)
    idempotent_hint: bool | None = None
    execution_hint: ExecutionHint = ExecutionHint.BACKEND


@dataclass(frozen=True)
class Definition:
    """Describes a tool. ``envelope`` is the executable authority source."""

    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] | None = None
    annotations: Annotations = field(default_factory=Annotations)
    envelope: Envelope = field(default_factory=Envelope)

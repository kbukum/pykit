"""Authorization decision protocol for agentic activation/invocation."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class HitlSource(enum.StrEnum):
    """Independent HITL trigger source."""

    TOOL_SENSITIVE_INVOCATION = "tool.sensitive_invocation"
    SKILL_HUMAN_APPROVAL = "skill.human_approval"


@dataclass(frozen=True, slots=True)
class DecisionRequest:
    """Generic authorization decision request."""

    principal: str
    action: str
    resource: str
    scopes: tuple[str, ...] = ()
    context: dict[str, object] = field(default_factory=dict)
    hitl_sources: tuple[HitlSource, ...] = ()


@dataclass(frozen=True, slots=True)
class Decision:
    """Authorization decision with optional independent HITL requirements."""

    allowed: bool
    reason: str = ""
    hitl_required: tuple[HitlSource, ...] = ()


@runtime_checkable
class Decider(Protocol):
    """Async authorization decider Protocol consumed by agent/MCP/skill."""

    async def decide(self, request: DecisionRequest) -> Decision:
        """Return an authorization decision for the supplied request."""

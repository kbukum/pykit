"""HITL sensitivity evaluation and human approval seams (D10).

A SensitivityEvaluator inspects a tool invocation's validated input against the
tool's declared sensitive-invocation predicates and returns one of:

* ``Decision.ALLOW`` — proceed without elevation.
* ``Decision.DENY`` — refuse the invocation outright.
* ``Decision.REQUIRE_APPROVAL`` — escalate to a human approver.

A HumanApproval seam adjudicates ``REQUIRE_APPROVAL`` decisions. The default
implementations are deny-by-default: they refuse every sensitive invocation
until an operator wires in a real evaluator/approver.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pykit_ai import JsonValue
from pykit_tool.definition import Envelope, SensitiveMatcher, SensitivePredicate

JsonObject = dict[str, JsonValue]


class Decision(StrEnum):
    """HITL evaluation outcome."""

    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True, slots=True)
class ToolCall:
    """Lean view of a tool invocation passed to the evaluator and approver."""

    tool_name: str
    arguments: JsonObject
    envelope: Envelope


@runtime_checkable
class SensitivityEvaluator(Protocol):
    """Adjudicates whether a tool call is sensitive enough to escalate."""

    async def evaluate(self, call: ToolCall, predicate: SensitivePredicate) -> Decision: ...


@runtime_checkable
class HumanApproval(Protocol):
    """Adjudicates a ``REQUIRE_APPROVAL`` decision via a human-in-the-loop."""

    async def approve(self, call: ToolCall) -> bool: ...


class DenyOnSensitiveEvaluator:
    """Default: any matching predicate denies the invocation."""

    async def evaluate(self, call: ToolCall, predicate: SensitivePredicate) -> Decision:
        if _predicate_matches(predicate, call.arguments):
            return Decision.DENY
        return Decision.ALLOW


class RequireApprovalEvaluator:
    """Optional: any matching predicate escalates to ``HumanApproval``."""

    async def evaluate(self, call: ToolCall, predicate: SensitivePredicate) -> Decision:
        if _predicate_matches(predicate, call.arguments):
            return Decision.REQUIRE_APPROVAL
        return Decision.ALLOW


class DenyHumanApproval:
    """Default: refuse every escalated invocation."""

    async def approve(self, call: ToolCall) -> bool:
        return False


async def evaluate_envelope(
    evaluator: SensitivityEvaluator,
    call: ToolCall,
) -> Decision:
    """Evaluate every predicate in the envelope; the strongest decision wins.

    Order of strength: ``DENY`` > ``REQUIRE_APPROVAL`` > ``ALLOW``.
    """
    strongest = Decision.ALLOW
    for predicate in call.envelope.sensitive_invocations:
        decision = await evaluator.evaluate(call, predicate)
        if decision is Decision.DENY:
            return Decision.DENY
        if decision is Decision.REQUIRE_APPROVAL:
            strongest = Decision.REQUIRE_APPROVAL
    return strongest


def _predicate_matches(predicate: SensitivePredicate, arguments: JsonObject) -> bool:
    """Apply a predicate matcher against the validated arguments dict.

    The ``jsonpath`` field accepts dotted segments (``a.b.c``) into nested dicts.
    Lists are not traversed; compose multiple predicates if richer paths are
    needed.
    """
    value = _resolve_path(arguments, predicate.jsonpath)
    match predicate.matcher:
        case SensitiveMatcher.EXISTS:
            return value is not None
        case SensitiveMatcher.EQUALS:
            return value == predicate.value
        case SensitiveMatcher.REGEX:
            if not isinstance(value, str) or not isinstance(predicate.value, str):
                return False
            import re

            return re.search(predicate.value, value) is not None
        case SensitiveMatcher.GT:
            return _compare_numeric(value, predicate.value, lambda a, b: a > b)
        case SensitiveMatcher.LT:
            return _compare_numeric(value, predicate.value, lambda a, b: a < b)


def _resolve_path(payload: JsonObject, path: str) -> JsonValue | None:
    cursor: JsonValue | None = payload
    for segment in path.split("."):
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(segment)
    return cursor


def _compare_numeric(
    left: JsonValue | None,
    right: str | int | float | bool | None,
    op: object,
) -> bool:
    if not isinstance(left, (int, float)) or isinstance(left, bool):
        return False
    if not isinstance(right, (int, float)) or isinstance(right, bool):
        return False
    return bool(op(left, right))  # type: ignore[operator]


__all__ = [
    "Decision",
    "DenyHumanApproval",
    "DenyOnSensitiveEvaluator",
    "HumanApproval",
    "RequireApprovalEvaluator",
    "SensitivityEvaluator",
    "ToolCall",
    "evaluate_envelope",
]

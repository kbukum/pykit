"""Tests for HITL sensitivity evaluation."""

from __future__ import annotations

import pytest

from pykit_tool import (
    Decision,
    DenyHumanApproval,
    DenyOnSensitiveEvaluator,
    Envelope,
    RequireApprovalEvaluator,
    SensitiveMatcher,
    SensitivePredicate,
    ToolCall,
    evaluate_envelope,
)


@pytest.mark.asyncio
async def test_deny_on_sensitive_blocks_matching_predicate() -> None:
    envelope = Envelope(
        sensitive_invocations=(SensitivePredicate(jsonpath="amount", matcher=SensitiveMatcher.GT, value=100),)
    )
    call = ToolCall(tool_name="x", arguments={"amount": 200}, envelope=envelope)
    decision = await evaluate_envelope(DenyOnSensitiveEvaluator(), call)
    assert decision is Decision.DENY


@pytest.mark.asyncio
async def test_deny_on_sensitive_allows_non_matching() -> None:
    envelope = Envelope(
        sensitive_invocations=(SensitivePredicate(jsonpath="amount", matcher=SensitiveMatcher.GT, value=100),)
    )
    call = ToolCall(tool_name="x", arguments={"amount": 50}, envelope=envelope)
    decision = await evaluate_envelope(DenyOnSensitiveEvaluator(), call)
    assert decision is Decision.ALLOW


@pytest.mark.asyncio
async def test_require_approval_escalates() -> None:
    envelope = Envelope(
        sensitive_invocations=(SensitivePredicate(jsonpath="path", matcher=SensitiveMatcher.EXISTS),)
    )
    call = ToolCall(tool_name="x", arguments={"path": "/etc/secret"}, envelope=envelope)
    decision = await evaluate_envelope(RequireApprovalEvaluator(), call)
    assert decision is Decision.REQUIRE_APPROVAL


@pytest.mark.asyncio
async def test_default_human_approver_denies() -> None:
    approver = DenyHumanApproval()
    envelope = Envelope()
    call = ToolCall(tool_name="x", arguments={}, envelope=envelope)
    assert await approver.approve(call) is False


@pytest.mark.asyncio
async def test_equals_matcher() -> None:
    envelope = Envelope(
        sensitive_invocations=(
            SensitivePredicate(jsonpath="env", matcher=SensitiveMatcher.EQUALS, value="prod"),
        )
    )
    call = ToolCall(tool_name="x", arguments={"env": "prod"}, envelope=envelope)
    assert await evaluate_envelope(DenyOnSensitiveEvaluator(), call) is Decision.DENY


@pytest.mark.asyncio
async def test_nested_jsonpath() -> None:
    envelope = Envelope(
        sensitive_invocations=(
            SensitivePredicate(jsonpath="config.region", matcher=SensitiveMatcher.EQUALS, value="us-east-1"),
        )
    )
    call = ToolCall(tool_name="x", arguments={"config": {"region": "us-east-1"}}, envelope=envelope)
    assert await evaluate_envelope(DenyOnSensitiveEvaluator(), call) is Decision.DENY

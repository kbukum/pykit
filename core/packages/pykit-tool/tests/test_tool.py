from __future__ import annotations

import asyncio

import pytest

from pykit_tool import (
    Annotations,
    BatchOptions,
    Context,
    DataClassification,
    Definition,
    Envelope,
    ExecutionHint,
    FilesystemMode,
    FilesystemRule,
    NetworkPolicy,
    NetworkRule,
    Registry,
    Safety,
    SensitiveMatcher,
    SensitivePredicate,
    SubprocessRule,
    chain,
    tool,
)


def test_definition_has_default_deny_envelope() -> None:
    definition = Definition(name="demo", description="Demo")
    assert definition.envelope.scopes == ()
    assert definition.envelope.network.rules == ()
    assert definition.envelope.filesystem == ()
    assert definition.envelope.subprocess == ()
    assert definition.envelope.safety is Safety.READ_ONLY
    assert definition.envelope.data_classification is DataClassification.PUBLIC


def test_annotations_are_non_executable_metadata() -> None:
    definition = Definition(
        name="ui_picker",
        description="Pick in UI",
        annotations=Annotations(title="Picker", execution_hint=ExecutionHint.UI),
    )
    assert definition.annotations.title == "Picker"
    assert definition.annotations.execution_hint is ExecutionHint.UI
    assert definition.envelope.safety is Safety.READ_ONLY


def test_envelope_models_for_normative_schema() -> None:
    envelope = Envelope(
        scopes=("db:read",),
        network=NetworkPolicy(rules=(NetworkRule(host=".example.com", port=443),)),
        filesystem=(FilesystemRule(path="/data/**", mode=FilesystemMode.READ),),
        subprocess=(SubprocessRule(argv_pattern=("git", "status"), env_allow=("LANG",)),),
        safety=Safety.MUTATING,
        sensitive_invocations=(SensitivePredicate(jsonpath="$.email", matcher=SensitiveMatcher.EXISTS),),
        data_classification=DataClassification.PII,
    )
    assert envelope.network.rules[0].scheme == "https"
    assert envelope.safety is Safety.MUTATING


@pytest.mark.asyncio
async def test_registry_call_batch_uses_caller_concurrency() -> None:
    active = 0
    peak = 0

    @tool(description="Sleep", envelope=Envelope(safety=Safety.READ_ONLY))
    async def sleep_tool(n: int) -> int:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return n

    registry = Registry()
    registry.register(sleep_tool.as_callable())
    results = await registry.call_batch(
        [("sleep_tool", {"n": 1}), ("sleep_tool", {"n": 2}), ("sleep_tool", {"n": 3})],
        Context(),
        BatchOptions(concurrency=2, fail_fast=False),
    )
    assert [result.content for result in results] == ["1", "2", "3"]
    assert peak == 2


def test_filter_by_typed_execution_hint() -> None:
    @tool(description="Search", annotations=Annotations(execution_hint=ExecutionHint.UI))
    async def search(query: str) -> str:
        return query

    registry = Registry()
    registry.register(search.as_callable())
    assert [definition.name for definition in registry.filter_by_execution_hint(ExecutionHint.UI)] == [
        "search"
    ]
    assert registry.filter_by_execution_hint(ExecutionHint.BACKEND) == []


def test_chain_without_local_policy_middleware() -> None:
    def identity(callable_tool):
        return callable_tool

    combined = chain(identity)
    assert callable(combined)

"""Registry — concurrent-safe collection of callable tools."""

from __future__ import annotations

import asyncio
import builtins
import threading
from dataclasses import dataclass

from pykit_ai import JsonValue
from pykit_resilience import Policy
from pykit_tool.callable import Callable
from pykit_tool.context import Context
from pykit_tool.definition import Definition, ExecutionHint
from pykit_tool.result import Result, error_result
from pykit_tool.sensitivity import (
    Decision,
    DenyHumanApproval,
    DenyOnSensitiveEvaluator,
    HumanApproval,
    SensitivityEvaluator,
    ToolCall,
    evaluate_envelope,
)
from pykit_tool.tool import ToolExecutionError

JsonObject = dict[str, JsonValue]


@dataclass(frozen=True, slots=True)
class BatchOptions:
    """Caller-owned batch execution policy."""

    concurrency: int = 1
    fail_fast: bool = False


class SensitivityDeniedError(RuntimeError):
    """Raised when a sensitivity evaluator denies a tool invocation."""


class HumanApprovalDeniedError(RuntimeError):
    """Raised when a human approver refuses an escalated invocation."""


class Registry:
    """Thread-safe registry of callable tools.

    ``with_tool_policy(name, policy)`` registers a per-tool resilience override
    that wraps ``call()`` for the named tool only.
    """

    def __init__(
        self,
        *,
        sensitivity_evaluator: SensitivityEvaluator | None = None,
        human_approval: HumanApproval | None = None,
        policy: Policy | None = None,
    ) -> None:
        self._tools: dict[str, Callable] = {}
        self._tool_policies: dict[str, Policy] = {}
        self._lock = threading.RLock()
        self._sensitivity = sensitivity_evaluator or DenyOnSensitiveEvaluator()
        self._approval = human_approval or DenyHumanApproval()
        self._policy = policy

    def register(self, tool: Callable) -> None:
        """Register a tool. Raises ValueError on duplicate names."""
        name = tool.definition.name
        if not name:
            msg = "tool name must be non-empty"
            raise ValueError(msg)
        with self._lock:
            if name in self._tools:
                msg = f"tool already registered: {name!r}"
                raise ValueError(msg)
            self._tools[name] = tool

    def with_tool_policy(self, name: str, policy: Policy) -> None:
        """Register a per-tool resilience policy override."""
        with self._lock:
            self._tool_policies[name] = policy

    def get(self, name: str) -> Callable | None:
        """Get a tool by name, or None if not found."""
        with self._lock:
            return self._tools.get(name)

    def list(self) -> list[Definition]:
        """List all registered tool definitions."""
        with self._lock:
            return [t.definition for t in self._tools.values()]

    def names(self) -> builtins.list[str]:
        """List all registered tool names."""
        with self._lock:
            return list(self._tools.keys())

    def search(self, query: str) -> builtins.list[Definition]:
        """Search tools by name or description substring (case-insensitive)."""
        q = query.lower()
        with self._lock:
            return [
                t.definition
                for t in self._tools.values()
                if q in t.definition.name.lower() or q in t.definition.description.lower()
            ]

    def filter_by_execution_hint(self, hint: ExecutionHint) -> builtins.list[Definition]:
        """Return tools whose annotations match the given execution_hint."""
        with self._lock:
            return [
                t.definition for t in self._tools.values() if t.definition.annotations.execution_hint == hint
            ]

    async def call(self, name: str, ctx: Context, input_data: JsonObject) -> Result:
        """Call a tool by name.

        Order of evaluation: sensitivity → (if RequireApproval) human approval →
        resilience policy → invoke. Authz is the caller's responsibility (e.g.,
        the MCP server applies it before calling here).
        """
        tool = self.get(name)
        if tool is None:
            msg = f"tool not found: {name!r}"
            raise KeyError(msg)

        call = ToolCall(tool_name=name, arguments=input_data, envelope=tool.definition.envelope)
        decision = await evaluate_envelope(self._sensitivity, call)
        if decision is Decision.DENY:
            raise SensitivityDeniedError(f"sensitive invocation denied: {name!r}")
        if decision is Decision.REQUIRE_APPROVAL and not await self._approval.approve(call):
            raise HumanApprovalDeniedError(f"human approval denied: {name!r}")

        with self._lock:
            policy = self._tool_policies.get(name, self._policy)

        async def _invoke() -> Result:
            return await tool.call(ctx, input_data)

        if policy is None:
            return await _invoke()
        return await policy.execute(_invoke)

    async def call_batch(
        self,
        calls: builtins.list[tuple[str, JsonObject]],
        ctx: Context,
        options: BatchOptions | None = None,
    ) -> builtins.list[Result]:
        """Execute calls with caller-supplied concurrency and fail-fast policy."""
        opts = options or BatchOptions()
        if opts.concurrency < 1:
            msg = "batch concurrency must be >= 1"
            raise ValueError(msg)
        semaphore = asyncio.Semaphore(opts.concurrency)
        results: list[Result | None] = [None] * len(calls)

        async def _run(index: int, tool_name: str, input_data: JsonObject) -> None:
            async with semaphore:
                try:
                    results[index] = await self.call(tool_name, ctx, input_data)
                except KeyError:
                    if opts.fail_fast:
                        raise
                    results[index] = error_result(f"tool not found: {tool_name!r}")
                except (SensitivityDeniedError, HumanApprovalDeniedError) as exc:
                    if opts.fail_fast:
                        raise
                    results[index] = error_result(str(exc))
                except ToolExecutionError as exc:
                    if opts.fail_fast:
                        raise
                    results[index] = error_result(str(exc))

        await asyncio.gather(*(_run(i, n, inp) for i, (n, inp) in enumerate(calls)))
        return [r if r is not None else error_result("tool call did not complete") for r in results]

    def __len__(self) -> int:
        with self._lock:
            return len(self._tools)

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._tools


__all__ = [
    "BatchOptions",
    "HumanApprovalDeniedError",
    "Registry",
    "SensitivityDeniedError",
]

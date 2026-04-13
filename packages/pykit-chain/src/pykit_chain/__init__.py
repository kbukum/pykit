"""pykit-chain — Sequential chain execution pattern.

Provides a composable way to run a sequence of async operations where each
step receives the output of the previous step.  Supports per-step progress
reporting, cancellation via ``asyncio.Event``, and automatic cleanup of
completed steps when a later step fails.

Mirrors gokit/chain (Go) and rskit-chain (Rust).

Quick start::

    chain = ChainBuilder().step(my_first_op).step(my_second_op).build()
    result = await chain.execute(initial_input)
"""

from __future__ import annotations

from pykit_chain.builder import ChainBuilder
from pykit_chain.executor import ChainConfig, ChainExecutor
from pykit_chain.operation import Operation
from pykit_chain.types import ChainResult, StepProgress, StepResult, StepStatus

__all__ = [
    "ChainBuilder",
    "ChainConfig",
    "ChainExecutor",
    "ChainResult",
    "Operation",
    "StepProgress",
    "StepResult",
    "StepStatus",
]

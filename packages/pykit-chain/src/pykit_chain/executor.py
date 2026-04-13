"""Sequential chain executor."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pykit_chain.operation import Operation
from pykit_chain.types import ChainResult, StepProgress, StepResult, StepStatus

logger = logging.getLogger(__name__)

ChainProgressFn = Callable[[StepProgress], None]


@dataclass
class ChainConfig:
    """Configuration for chain execution."""

    cleanup_on_failure: bool = True
    stop_on_failure: bool = True


class ChainExecutor:
    """Executes a sequence of operations, passing each output as input to the next."""

    def __init__(
        self,
        operations: list[Operation],
        config: ChainConfig | None = None,
    ) -> None:
        self._operations = operations
        self._config = config or ChainConfig()

    async def execute(
        self,
        input: Any,
        progress: ChainProgressFn | None = None,
        cancel: asyncio.Event | None = None,
    ) -> ChainResult:
        """Execute all operations sequentially.

        Args:
            input: Initial input for the first step.
            progress: Optional callback for per-step progress updates.
            cancel: Optional event — when set, remaining steps are cancelled.

        Returns:
            :class:`ChainResult` with per-step results.
        """
        chain_start = time.monotonic()
        total_steps = len(self._operations)
        results: list[StepResult] = []
        current_input = input
        failed = False

        for i, op in enumerate(self._operations):
            # Check cancellation before starting each step
            if cancel is not None and cancel.is_set():
                for remaining in self._operations[i:]:
                    results.append(
                        StepResult(
                            step_id=remaining.id,
                            status=StepStatus.CANCELLED,
                            error="chain cancelled",
                        )
                    )
                break

            # Skip remaining if a previous step failed and stop_on_failure is true
            if failed and self._config.stop_on_failure:
                results.append(StepResult(step_id=op.id, status=StepStatus.SKIPPED))
                continue

            step_id = op.id
            step_start = time.monotonic()

            # Emit "running" progress
            if progress is not None:
                progress(
                    StepProgress(
                        step_index=i,
                        step_id=step_id,
                        status=StepStatus.RUNNING,
                        progress_percent=0,
                    )
                )

            # Create per-step progress wrapper
            def _step_progress(pct: int, msg: str | None = None, *, _i: int = i, _sid: str = step_id) -> None:
                if progress is not None:
                    progress(
                        StepProgress(
                            step_index=_i,
                            step_id=_sid,
                            status=StepStatus.RUNNING,
                            progress_percent=pct,
                            message=msg,
                        )
                    )

            logger.debug(
                "executing chain step",
                extra={"step": step_id, "index": i, "total_steps": total_steps},
            )

            try:
                output = await op.execute(current_input, _step_progress)
            except Exception as exc:
                duration = time.monotonic() - step_start
                logger.error("chain step failed", extra={"step": step_id, "error": str(exc)})

                if progress is not None:
                    progress(
                        StepProgress(
                            step_index=i,
                            step_id=step_id,
                            status=StepStatus.FAILED,
                            progress_percent=0,
                            message=str(exc),
                        )
                    )

                results.append(
                    StepResult(
                        step_id=step_id,
                        status=StepStatus.FAILED,
                        duration=duration,
                        error=str(exc),
                    )
                )
                failed = True
            else:
                duration = time.monotonic() - step_start

                if progress is not None:
                    progress(
                        StepProgress(
                            step_index=i,
                            step_id=step_id,
                            status=StepStatus.COMPLETED,
                            progress_percent=100,
                        )
                    )

                current_input = output
                results.append(
                    StepResult(
                        step_id=step_id,
                        status=StepStatus.COMPLETED,
                        duration=duration,
                        output=output,
                    )
                )

        # Cleanup on failure: call cleanup on completed steps in reverse order
        all_completed = all(r.status == StepStatus.COMPLETED for r in results) and len(results) == total_steps

        if not all_completed and self._config.cleanup_on_failure:
            logger.warning("chain failed, cleaning up completed steps")
            for result in reversed(results):
                if result.status != StepStatus.COMPLETED:
                    continue
                for op in self._operations:
                    if op.id == result.step_id:
                        try:
                            await op.cleanup(result.output)
                        except Exception:
                            logger.exception("cleanup failed for step %s", result.step_id)
                        break

        total_duration = time.monotonic() - chain_start
        final_output = results[-1].output if all_completed and results else None

        return ChainResult(
            steps=results,
            total_duration=total_duration,
            final_output=final_output,
            success=all_completed,
        )

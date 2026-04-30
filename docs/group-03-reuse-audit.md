# Group 03 pykit reuse audit

Scope: `pykit-resilience`, `pykit-pipeline`, `pykit-chain`, `pykit-dag`, `pykit-worker`, `pykit-process`, `pykit-stateful`.

| File:line | Recommended action | Justification |
|---|---|---|
| `packages/pykit-pipeline/src/pykit_pipeline/base.py:663` | Leave | `asyncio.sleep` implements debounce timing, not retry/backoff; no resilience primitive duplication. |
| `packages/pykit-worker/src/pykit_worker/ticker.py:114` | Leave | Periodic ticker cadence is scheduling behavior, not backoff/rate-limit/timeout policy. |
| `packages/pykit-worker/src/pykit_worker/pool.py:123` | Leave | Caller-supplied wait timeout is an observation timeout for `wait()`, not task execution policy. |
| `packages/pykit-worker/src/pykit_worker/pool.py:276` | Align | Worker task execution timeout duplicates the canonical timeout primitive; future cleanup should inject/consume `pykit_resilience.Policy` or its timeout wrapper. |
| `packages/pykit-process/src/pykit_process/runner.py:36` | Leave | Subprocess wall-clock timeout is process lifecycle control with signal cleanup, not a generic resilience timeout. |
| `packages/pykit-process/src/pykit_process/runner.py:125` | Leave | Grace-period wait is termination protocol timing, not resilience retry/timeout duplication. |
| `packages/pykit-process/src/pykit_process/runner.py:130` | Leave | Final post-SIGKILL wait bounds cleanup after process termination. |
| `packages/pykit-dag/src/pykit_dag/engine.py:61` | Align | DAG execution timeout duplicates the canonical timeout primitive; future cleanup should compose through `pykit_resilience.Policy` when layer rules allow. |
| `packages/pykit-stateful/src/pykit_stateful/manager.py:129` | Leave | Cleanup loop cadence is TTL housekeeping, not backoff/rate-limit/timeout policy. |
| `packages/pykit-stateful/src/pykit_stateful/accumulator.py:152` | Leave | TTL sweep interval is local eviction scheduling and already lock-correct. |
| `packages/pykit-chain` | Leave | Package is absent in this checkout; no pykit-chain findings to record. |

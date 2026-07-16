# Pass 02 — Principle conformance

Each item here is a hard principle from
[`.github/copilot-instructions.md`](../../../copilot-instructions.md), not a preference. This is
where vibe coding drifts most — especially around resilience, async/concurrency, and composition.

> **Run in a separate, clean-context agent** — never inline in the session that wrote the code.
> An independent reviewer re-derives every judgment from the code and the principles instead of
> trusting prior reasoning. A plan/spec may be passed in as a scope checklist only; it never
> excuses a baseline violation.

**Scope note.** *Changes mode:* grep the touched packages and reason about each runtime path.
*Project mode:* the error/concurrency/composition invariants below hold across the whole library
surface — sweep the tree.

## Typed, minimal APIs

Public surfaces are fully typed and minimal: no broad `Any`, untyped `object`, unchecked `cast()`,
or untyped `dict`/`list` escape hatch except genuinely opaque values (JSON payload, plugin-owned
metadata, third-party callback contract) — and those are documented. Prefer PEP 695 generics,
`Protocol`s, typed enums, frozen dataclasses, and pydantic v2 models. Actionable typed errors
(`AppError`) preserve cause via `raise ... from e`. No incidental public identifiers or root
facade re-exports; private helpers stay underscored.

## Errors & resilience

- No swallowed failures (`except Exception: pass`), bare broad catches that return success-shaped
  fallbacks, or re-raises that lose cause. Use typed `AppError` with a meaningful code and
  `raise ... from e` when translating exceptions.
- No success-shaped fallbacks that mask failure (returning an empty model/list/string on a real
  failure unless that is the documented behavior and observable to callers).
- Every remote call has a **timeout** (`asyncio.timeout`, anyio timeout scopes, or a configured
  client timeout). Retries are **bounded, jittered, and applied to idempotent ops only**. Failures
  circuit-break and degrade gracefully rather than hang or cascade. (Reuse `pykit-resilience` —
  see pass `01`.)

## Async and concurrency

- Every task has clear **ownership, cancellation, timeout, and shutdown** handling; no task leaks
  (a fire-and-forget `asyncio.create_task()` with no stop path is a **blocker**).
- Queues / buffers / concurrency are **bounded with documented backpressure**; components **drain
  in-flight work on shutdown**. An unbounded queue on an ingest path is a **blocker**.
- Shared state is guarded or task-confined. Cancellation is not swallowed by broad exception
  handlers. Prefer structured concurrency (`asyncio.TaskGroup` or anyio task groups) over loose
  task spawning. Time-dependent paths use injected clocks/time providers, not wall-clock sleeps.

## Composition

- Registries and policies are **explicitly injected**; selection is config-driven.
- **No import-time side effects, no mutable module-level registries**, no reaching for a global
  logger/tracer — inject them. A module-level dict registry mutated at runtime, or import-time code
  that dials network / reads env / registers into a global, is a **blocker**.
- Constructors take explicit typed dependencies and options; dependencies are passed in, not
  resolved from a stringly service locator at call sites.

## Currency

Current Python idioms, not folklore (also enforced in pass `01`). Python 3.13+ built-in generics
and PEP 695 type parameters where appropriate; pydantic v2, not v1; `asyncio`/anyio, not mixed
threading for async IO; `httpx` for async HTTP when a pykit owner is not the right abstraction;
`structlog` or std `logging`, not `print()` in libraries; `ruff` + `mypy --strict` clean. Flag
superseded patterns such as mutable defaults, `typing.List`/`Dict` in new code, broad `Any`, and
untyped decorators that erase signatures.

## AI / model features (only if the change touches them)

Model output and retrieved context are **untrusted**; outputs are structured/validated; tool
calls are least-privilege with a **human gate on destructive actions**; prompts/models are
versioned and changes gated on evals.

## Detection starters

Exclude tests when judging runtime-path hits unless the test helper itself is public reusable
library code.

```bash
rg -n 'Any|object\]|object\)|cast\(|type:\s*ignore|#\s*pyright:\s*ignore' . -g '*.py'
rg -n 'except Exception:\s*pass|except BaseException|raise$|raise [A-Za-z_][A-Za-z0-9_]*\(' . -g '*.py'
rg -n 'asyncio\.create_task|asyncio\.Queue\(|Queue\(|Semaphore\(|time\.sleep|asyncio\.sleep' . -g '*.py'
rg -n '^(REGISTRY|registry|_registry)\s*=|^.*=\s*\{\}\s*$|load_dotenv\(|os\.environ\[' . -g '*.py'
rg -n 'print\(|logging\.basicConfig\(|requests\.' . -g '*.py'
```

# pykit

Async Python infrastructure kit using a uv workspace: `core/packages/` foundations, `contrib/` adapters, and a lazy `pykit` facade. Read versions, workspace membership, and configured checks from `pyproject.toml` and the Makefile.

## Invariants

- Pre-stable: redesign root causes rather than preserving flawed APIs with shims. Choose Redesign / Align / Enhance / Drop for defects; leave sound code alone.
- Reuse or enhance the canonical lower-layer owner. No upward runtime imports or cross-kit runtime dependency; implement lower-layer Protocols and inject behavior. Check import-linter contracts rather than assuming a copied package table is current.
- Use typed minimal APIs, PEP 695/built-in generics, Protocols rather than ABCs, frozen dataclasses or Pydantic models, and cause-preserving `AppError`. No blanket catches, swallowed errors, or success-shaped fallbacks.
- Async-first; explicit injected registries and config-selected adapters. No import-time I/O, environment reads, or mutable global registries. Provider shapes: RequestResponse, Stream, Sink, Duplex.
- Validate trust boundaries and untrusted model output; no secrets in source/logs or credential URLs. Use least privilege, parameterized SQL, and argv-only subprocesses.
- Bound remote calls, idempotent jittered retries, queues, and task concurrency. Every coroutine/resource has ownership, cancellation, and teardown.
- Test-first, deterministic behavior and failures; reuse shared helpers, inject clocks, seed RNG. Unit doubles do not prove real integrations. Coverage: >=80% per package, >=85% overall and for errors/auth/authz/security/resilience/encryption. Never lower gates.
- Follow Ruff, strict mypy, and Google-style docstrings. Markdown prose has no hard column wrapping; document current behavior.

## Work and validation

Use only the matching [skill](skills/README.md) and needed reference sections. Preserve user edits/index. Commit, amend, push, publish, or open draft PRs only when authorized. Reviews remain read-only unless fixing was requested. Keep multi-step recovery in `tmp/plans/<task>/handoff.md`; load current work and needed dependency contracts, not all historical steps.

Use the [validate skill](skills/validate/SKILL.md) for scoped `make`/`uv` commands. The project uses pytest, Ruff, strict mypy, and import-linter. Run required full gates at acceptance, not after every edit. Prose-only edits need link/metadata checks.

Before changing package layout, facade exports, or adapters, read the matching `new-package` / `new-backend` skill and current manifests. For security, AI, dependency, or release changes, read the relevant [engineering principles](engineering.md#engineering-principles) and task checklist. The [reference](engineering.md) supplies detail on demand, not another startup payload.

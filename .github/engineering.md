# pykit engineering reference

Read only the relevant section; the [agent entry point](copilot-instructions.md) supplies the shared invariants.

## Engineering principles

Reuse the owning package before adding behavior. Consume lower-layer APIs; implement lower-layer Protocols for injected higher-layer behavior. No upward runtime imports, global registries, import-time I/O, or duplicated infrastructure. Capability parity does not require identical internal APIs.

Runtime errors preserve typed codes and causes; no blanket swallowing or successful-looking fallback. Every remote call has a timeout, one bounded idempotent retry owner, and cancellation. Queues/tasks/streams are bounded and have documented overflow/drain/teardown behavior.

Validate untrusted inputs, use parameterized SQL and argv-only subprocesses, and keep credentials out of URLs/logs/fixtures. Minimize/redact sensitive data and bound retention. Model/retrieved output needs schema validation; tool actions need authorization and destructive-action approval. Version prompts/models/schemas and gate changes with representative/adversarial evals.

Dependencies need maintenance/advisory/license checks; CI actions use full SHAs. Release artifacts retain signing, SBOM, provenance, and trusted publishing. Check actual automation rather than assuming documentation proves a gate exists.

## Build, Test, and Lint

`core/` and `contrib/` have separate `pyproject.toml` and lockfiles; there is no root Python project. The root Makefile routes `P=<package>`, `W=core|contrib|both`, and `T=<pytest-pattern>`. Use the [validate skill](skills/validate/SKILL.md) for commands.

Run package build, pytest, Ruff, mypy, and architecture checks as applicable; full `make check` is fmt-check/lint/typecheck/test. Refresh dependencies from the owning workspace. Documentation-only edits do not need runtime suites.

Coverage policy is >=80% per package and >=85% overall/security-load-bearing modules. Inspect current coverage configuration and measured results: configured floors can differ from policy, and a weaker green gate does not prove acceptance.

## Package Structure

Foundation packages live in `core/packages/pykit-<name>/`; technology adapters in `contrib/pykit-<domain>-<name>/`. `core/packages/pykit` owns the lazy facade. Keep optional drivers out of core defaults.

Use `domains.toml` and each workspace's import-linter contracts for the actual layer map, not a copied list. New packages need workspace/dev-group membership, correct facade exposure where appropriate, package docs, tests, and lock updates. See [new-package](skills/new-package/SKILL.md) and [new-backend](skills/new-backend/SKILL.md).

## Code Style

Use workspace Ruff settings, strict mypy, Google-style docstrings, built-in/PEP 695 generics, Protocols, frozen dataclasses or Pydantic v2 models, and async/await. Public opaque values require a documented reason. Keep files concern-focused and public surfaces minimal.

## Key Patterns

`AppError` carries typed codes and cause; transport-specific status mapping stays at the transport boundary. Pydantic Settings owns config loading. Component start/stop/health follows registry order. Providers use RequestResponse, Stream, Sink, or Duplex; pipelines use async pull iterators. Test with shared helpers, injected clocks, seeded randomness, and explicit failure/cleanup assertions.

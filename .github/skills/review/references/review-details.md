# Review and apply fixes

Use only when fixes are requested. Follow [review](../SKILL.md) and the [baseline](../../../copilot-instructions.md). Preserve edits/index; review directly unless an independent agent is requested.

## Scope

Inspect the requested diff or tree and its close callers/callees. Flag workspace manifests/locks, `domains.toml`, import-linter contracts, shared errors, facade exports, and adapter impacts. `core/` and `contrib/` own separate Python projects. Plans define scope, not exceptions.

## Passes

Use [validate](../../validate/SKILL.md) for scoped Makefile/uv gates. Load details only for applicable triggers.

| Pass | Trigger and checks | Detail |
|---|---|---|
| Placement/reuse | Packages, adapters, shared concerns; correct ownership and downward dependencies | [00](00-structure-placement.md), [01](01-canonical-reuse.md) |
| Correctness | Python behavior; typed causes, validated models, no broad unchecked values, mutable defaults, swallowed errors, or success fallbacks; context-managed cleanup | [02](02-principles.md), [04](04-quality.md) |
| Concurrency | Async/tasks/locks/pools; structured ownership, bounded concurrency/queues/drain, cancellation propagation, no unjustified lock across blocking calls, injected clocks | [02](02-principles.md), [05](05-tests-tdd.md) |
| Composition | Registries/components/factories; explicit injected selection, lifecycle order, opt-in contrib adapters, no global registry/logger or import-time I/O | [00](00-structure-placement.md), [02](02-principles.md) |
| Security/config | External input, auth, paths, crypto/config; bounded validation, SQL parameters, argv-only subprocesses, header credentials, JWT allowlists/required claims, current crypto and redaction | [03](03-security-privacy.md) |
| API/dependencies | Public items/manifests; minimal typed Protocols/generics, justified dependencies, locks/workspace/domain/import-linter/facade wiring | [01](01-canonical-reuse.md), [04](04-quality.md) |
| Tests/docs | Every scope; deterministic behavioral/failure proof, coverage, property tests where appropriate, current Google-style docstrings and examples | [05](05-tests-tdd.md), [06](06-docs-supply-chain.md), [07](07-comments-docstrings.md) |

Use shared fixtures, injected clocks, seeded randomness, `monkeypatch`, and `tmp_path`. Run only configured parallel/random-order tooling. Measure package/overall coverage; a report alone does not prove policy. Unit doubles do not replace required integrations. Prose-only work needs documentation checks, not runtime suites.

## Findings and acceptance

Report `severity — file:line — finding — principle — fix`, grouping patterns. Principle violations, wrong behavior, and broken contracts block acceptance. Explain skipped/deferred passes and evidence gaps.

Apply authorized root-cause fixes test-first and validate affected packages. Ask only for unresolved scope or behavior decisions. Commit/amend/push/PR require separate authorization.

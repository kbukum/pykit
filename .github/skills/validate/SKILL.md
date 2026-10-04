---
name: validate
description: "pykit: Run the repository's build, test, lint, and documentation gates scoped to the change."
user-invocable: true
---

# Validating pykit changes with make (ruff / mypy / pytest / import-linter)

pykit is a uv-workspace monorepo (`core/packages/`, `contrib/`) with 40+ packages. The `Makefile`
is the canonical task runner: it wraps `uv run` with package/workspace scoping. Prefer it over raw
`uv` for anything with a `make` target, and **always scope to what changed** — full-tree gates are
slow and belong to audits/CI sign-off.

## Golden rule: scope to what changed

Never run the whole tree for a small change. Scope by package (`P=`), by workspace
(`W=core|contrib|both`), or let the affected-set target compute the blast radius.

```bash
make test-affected                        # only packages the diff touches
make test-coverage P=<pkg>                # coverage for one package
```

## Core tasks

| Intent | Command | Notes |
|---|---|---|
| Build | `make build P=<pkg>` | `uv build`; `W=` for a whole workspace |
| Test | `make test P=<pkg> T=<pattern>` | pytest; `T=` maps to `-k` |
| Lint | `make lint P=<pkg>` | ruff check |
| Type-check | `make typecheck P=<pkg>` | mypy strict |
| Format (write) | `make fmt` | ruff format + `ruff check --fix` |
| Format (check) | `make fmt-check` | fast, ruff format --check |
| Coverage | `make test-coverage P=<pkg>` | Check package and overall policy thresholds, not only the configured floor |

## Scoping selectors

- `P=<pkg>` — one package by its full name, e.g. `P=pykit-storage` (core) or `P=pykit-storage-s3`
  (contrib). The Makefile resolves it under `core/packages/` or `contrib/` automatically.
- `W=core|contrib|both` — one workspace (default `both`).
- `T=<pattern>` — a pytest `-k` test-name filter.

```bash
make test P=pykit-di T=cycle                # one package, tests matching "cycle"
make lint W=core                            # ruff across the core workspace
make build P=pykit-server                   # one package
```

To stay scoped below what a `make` target offers, drive `uv` directly from the right workspace root:

```bash
cd core && uv run pytest packages/pykit-di/tests/ -k cycle
cd core && uv run mypy packages/pykit-di/src/
```

## Layering guard

pykit's layer direction (lower layers never import higher) is enforced by **import-linter** — cheap
and catches what the type checker won't. Run it on any structural change:

```bash
uv run --project core lint-imports --config core/pyproject.toml
uv run --project contrib lint-imports --config contrib/pyproject.toml
make check-<domain>                        # per-domain gate via scripts/check-domain.sh
```

Per-domain gates aggregate fmt/lint/typecheck/test for a slice of the tree:
`make check-core|check-patterns|check-crosscutting|check-composition|check-transport|check-auth|check-data|check-ai|check-media|check-infra`.

Coverage policy is >=80% per package and >=85% overall/security-load-bearing code. Check current `core/pyproject.toml` and `contrib/pyproject.toml`; their configured floors may differ. A green weaker gate alone does not meet policy. Run dependency audits from each applicable workspace, not a nonexistent root Python project.

## Before you hand work off

For a self-contained change, the minimum green bar is: `fmt-check`, `lint P=<pkg>`,
`typecheck P=<pkg>`, `test P=<pkg>` (async tests deterministic; parallel-safe under `-n auto`), and
`import-linter` on any structural change. Escalate to the full canonical gate only for audits or a
release:

```bash
make check                     # full canonical gate — fmt-check + lint + typecheck + test
uv run --project core pip-audit
uv run --project contrib pip-audit
```

Treat a green run as **necessary but not sufficient**: it does not catch unbounded concurrency,
missing timeouts/cancellation on async calls, `asyncio` task leaks, global-registry composition
smells, duplicated owners, or boundary-validation gaps. Those are on the reviewer.

Per repo workflow, **create the branch and make edits only** — the maintainer commits and pushes.

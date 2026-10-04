# Review project

Standing, re-runnable **whole-toolkit audit**, independent of any diff. Use it periodically,
before a release, when onboarding to a package/domain, or whenever you want assurance the tree as
a whole still honors the baseline. It sequences the same eight focused passes in
[`references/`](./) but over the existing code rather than a change set.

## Execution

Follow [the review skill](../SKILL.md): direct review by default; independent agents only on request. Read current source and relevant contracts. A plan is a scope checklist, not a justification for a baseline violation.

## Scope first to keep the audit tractable

The whole tree is large. Prefer auditing **one domain or package at a time** rather than
everything at once:

- a single package or domain (`pykit-errors`, `pykit-auth`, the `data` domain),
- a whole workspace (`core` vs `contrib`), or
- the full tree only when you have time for the slow gates.

State the chosen surface up front so findings are bounded.

## Pass 0 — Scope and context

- Get a structural picture before diving in: list packages, workspaces, and dependency edges; skim
  each package tree.

```bash
find core/packages contrib -maxdepth 2 -name pyproject.toml | sort
uv run --project core lint-imports --config core/pyproject.toml
uv run --project contrib lint-imports --config contrib/pyproject.toml
cat domains.toml
```

## Passes

Follow the trigger table and order in [the review skill](../SKILL.md). Use each checklist's project scope. Load applicable files only; report incomplete checks and stop acceptance on structural/reuse blockers.

## Findings

Record every finding as:

```text
severity (blocker / should-fix / nit) — file:line — what's wrong — which principle — suggested fix
```

Group findings by package and by pass so the report is actionable. See [`SKILL.md`](../SKILL.md)
for severity definitions.

## Validation

A full audit is the place for the slow, complete gates:

```bash
make fmt-check
make lint                 # whole-tree ruff check (or P=<package>)
make typecheck            # mypy strict (or P=<package>)
make test                 # pytest across core + contrib
make test-coverage        # coverage report; required policy thresholds
make check                # full canonical gate: fmt-check + lint + typecheck + test
uv run --project core lint-imports --config core/pyproject.toml
uv run --project contrib lint-imports --config contrib/pyproject.toml
uv run --project core pip-audit
uv run --project contrib pip-audit
```

A green `make check` is necessary but **not sufficient** — async task leaks, missing timeouts/
cancellation, unbounded queues, global-registry composition smells, duplicated owners, and
boundary-validation gaps are on the reviewer, not the gate.

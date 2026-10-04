# Review changes

Standing, re-runnable review of a **change set** in this repository — a branch, a commit range,
or `HEAD~1`. Use it after every change set, especially fast/"vibe-coded" work. It sequences the
eight focused passes in [`references/`](./) over a diff and adds scope handling; the actual checks
live in the focused files.

## Execution

Follow [the review skill](../SKILL.md): direct review by default; independent agents only on request. Read current source and relevant contracts. A plan is a scope checklist, not a justification for a baseline violation.

## Pass 0 — Scope and context

- Get the actual diff: `git diff <base>...HEAD --stat`, then per file. Review what changed
  **plus its blast radius** — the rest of each touched file, the code the change calls and is
  called by, and closely-related files in the same package. Do not audit the whole repo (that is
  [`review-project.md`](./review-project.md)), but do not tunnel-vision on the diff lines either.
- **Pre-existing problems in the blast radius are in scope.** A defect, dead code, duplicated
  concern, or design smell you read while reviewing is reported like any other finding — the
  change set is not a shield for the code around it. Because pykit is pre-stable with **no
  backward compatibility owed**, prefer a root-cause **redesign** over patching the symptom
  (decide Redesign / Align / Enhance / Drop; "leave it patched" is not an option). Flag when a
  fix reaches beyond the touched files and keep it coherent; never silently refactor unrelated
  code.
- pykit is a Python infrastructure toolkit: a change to a core package's public surface fans out
  to every core package, every contrib adapter, the root `pykit` lazy-loading facade, and sibling
  kit parity (aligned per capability with whichever kit is strongest in that scope; see
  `docs/parity-matrix.md`). List that blast radius before
  reviewing.
- Note whether the change belongs in **core** (`core/packages/pykit-<name>/`), a **contrib
  adapter** (`contrib/pykit-<name>/`), the root facade package (`core/packages/pykit/`), or a
  different package entirely.

## Passes

Follow the trigger table and order in [the review skill](../SKILL.md). Use each checklist's changes scope. Load applicable files only; report incomplete checks and stop acceptance on structural/reuse blockers.

## Findings

Record every finding as:

```text
severity (blocker / should-fix / nit) — file:line — what's wrong — which principle — suggested fix
```

See [`SKILL.md`](../SKILL.md) for severity definitions.

## Validation

**Scope every command to the changed package(s) — do not run the full-tree gates here.** pykit
has many uv-workspace packages; unscoped `make check` / `make test` / `make build` across both
workspaces are reserved for [`review-project.md`](./review-project.md) or final pre-merge
sign-off (typically in CI). For a change set, run only:

```bash
make fmt-check P=<package>              # ruff format --check, scoped
make lint P=<package>                   # ruff check, scoped
make typecheck P=<package>              # mypy strict, scoped
make test P=<package> T=<pattern>       # pytest, optionally narrowed by -k pattern
make test-affected                      # only packages the diff touches
make check-<domain>                     # scripts/check-domain.sh for a domain in domains.toml
```

Use raw scoped commands when needed, for example `cd core && uv run pytest packages/pykit-di/tests/
-k cycle`, `cd core && uv run mypy packages/pykit-di/src/`, or `uv run --project <workspace> lint-imports --config <workspace>/pyproject.toml` for layer
checks. Prefer `make test-affected` over unscoped targets — it runs only packages impacted by the
current changes. Step up to a per-domain `make check-<domain>` when the change spans a domain. Run
the full `make check` only when the change is genuinely tree-wide, or leave it to CI for sign-off.
A green scoped run is necessary but **not sufficient** — it will not catch async task leaks,
missing timeouts/cancellation, unbounded queues, global-registry composition smells, duplicated
owners, or boundary-validation gaps. Those are on the reviewer.

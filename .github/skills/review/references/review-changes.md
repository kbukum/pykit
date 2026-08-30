# Review changes

Standing, re-runnable review of a **change set** in this repository — a branch, a commit range,
or `HEAD~1`. Use it after every change set, especially fast/"vibe-coded" work. It sequences the
eight focused passes in [`references/`](./) over a diff and adds scope handling; the actual checks
live in the focused files.

## Run this in a separate, clean-context agent

**Always dispatch this review to a fresh reviewer agent with no shared session context.** A
reviewer that "remembers" writing the code rationalizes it; an independent agent re-derives
every judgment from the diff and the principles. Do not run it inline in the same session that
produced the change.

- Hand the reviewer agent: the diff (or base ref), this file, and the [`references/`](./) folder.
  Nothing else from the authoring session.
- The reviewer reads the code as-is; it does not trust prior reasoning about why the code
  "should" be correct.
- **Optional plan check.** If a plan/spec exists (for example, an issue or a design doc), pass it
  in *as a scope checklist only* — "here is what this change set claimed to do; verify the diff
  actually did it, with tests." The plan defines intended scope; it never excuses a principle
  violation. If the diff diverges from the plan, report the divergence; the baseline in
  [`.github/copilot-instructions.md`](../../../copilot-instructions.md) wins over any plan.

## Pass 0 — Scope and context

- Get the actual diff: `git diff <base>...HEAD --stat`, then per file. Review only what changed
  plus its blast radius; do not audit the whole repo (that is
  [`review-project.md`](./review-project.md)).
- pykit is a Python infrastructure toolkit: a change to a core package's public surface fans out
  to every core package, every contrib adapter, the root `pykit` lazy-loading facade, and sibling
  kit parity (aligned per capability with whichever kit is strongest in that scope; see
  `docs/parity-matrix.md`). List that blast radius before
  reviewing.
- Note whether the change belongs in **core** (`core/packages/pykit-<name>/`), a **contrib
  adapter** (`contrib/pykit-<name>/`), the root facade package (`core/packages/pykit/`), or a
  different package entirely.

## Passes — run in order, stop early on a structural failure

Work the focused files top to bottom. **Stop and reject as soon as a change fails pass `00` or
`01`** — misplaced or duplicated code makes every later pass moot.

1. [`00-structure-placement.md`](./00-structure-placement.md) — package placement, acyclic
   layering, `pyproject.toml`, package docstrings, and workspace/domain wiring.
2. [`01-canonical-reuse.md`](./01-canonical-reuse.md) — reuse vs. reimplementation of a
   package/stdlib-owned concern. *(blocker class)*
3. [`02-principles.md`](./02-principles.md) — typed/minimal APIs, errors & resilience,
   async/concurrency, composition, currency, AI features.
4. [`03-security-privacy.md`](./03-security-privacy.md) — trust-boundary validation, injection
   safety, token hygiene, crypto, data minimization.
5. [`04-quality.md`](./04-quality.md) — root-cause over patches, dead code, file/package
   organization, style gates.
6. [`05-tests-tdd.md`](./05-tests-tdd.md) — TDD, deterministic async/parallel tests, clock/env/cwd
   discipline, fixtures.
7. [`06-docs-supply-chain.md`](./06-docs-supply-chain.md) — docstrings/README, Conventional
   Commits, `uv.lock`, `pip-audit`, SHA-pinned actions, SBOM.
8. [`07-comments-docstrings.md`](./07-comments-docstrings.md) — comments and Google-style
   docstrings explain the code as it is; rewrite or delete plan/history/process prose.

Each focused file carries a "Changes mode" scope note — follow that mode here. When you only
need one lens (e.g. just security, just TDD), run that focused file directly instead of this
orchestrator.

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
-k cycle`, `cd core && uv run mypy packages/pykit-di/src/`, or `uv run import-linter` for layer
checks. Prefer `make test-affected` over unscoped targets — it runs only packages impacted by the
current changes. Step up to a per-domain `make check-<domain>` when the change spans a domain. Run
the full `make check` only when the change is genuinely tree-wide, or leave it to CI for sign-off.
A green scoped run is necessary but **not sufficient** — it will not catch async task leaks,
missing timeouts/cancellation, unbounded queues, global-registry composition smells, duplicated
owners, or boundary-validation gaps. Those are on the reviewer.

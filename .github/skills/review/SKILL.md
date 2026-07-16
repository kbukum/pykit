---
name: review
description: >-
    Run pykit's standing engineering-baseline review over a change set (a branch, commit range,
    or HEAD~1) or over a whole package/domain/tree. Sequences eight focused passes — structure &
    placement, canonical reuse, principles, security & privacy, quality, tests/TDD, docs & supply
    chain, comments & docstrings. Use before merging a change, when auditing a package, or before a
    release. Always run it in a fresh, clean-context reviewer.
user-invocable: true
---

# Reviewing pykit against its engineering baseline

pykit is shared foundation infrastructure and a **sibling kit** to rskit (the reference) and gokit:
a defect in a core package propagates to the `pykit` facade, the other core packages, every
`contrib/` adapter, and every downstream consumer. The bar is correspondingly high — security,
concurrency, and composition each get their own lens. This skill encodes pykit's permanent review
baseline as eight focused passes plus three orchestrators.

The authoritative baseline lives in
[`.github/copilot-instructions.md`](../../copilot-instructions.md). A plan, spec, issue, or roadmap
may be passed in **as a scope checklist only** — it defines intended scope, never excuses a baseline
violation. If the code diverges from the plan, report the divergence; the baseline wins.

## Run in a separate, clean-context agent

**Always dispatch a review to a fresh reviewer with no shared session context** — never inline in
the session that wrote the code. A reviewer that "remembers" writing the change rationalizes it;
an independent agent re-derives every judgment from the code and the principles. Hand it only the
scope (diff or package/domain) and this skill.

## Pick a driver

- **Change set** → [`references/review-changes.md`](references/review-changes.md). A diff (branch,
  commit range, or `HEAD~1`). Use after every change set, especially fast/"vibe-coded" work.
- **Whole tree / package** → [`references/review-project.md`](references/review-project.md). A
  standing audit independent of any diff. Use periodically, before a release, or when onboarding.
- **Review → fix in one pass** → [`references/review-details.md`](references/review-details.md).
  Fans the review into parallel subagent passes by Python concern, then plans and applies fixes.

## The eight focused passes (run in order)

Stop and reject as soon as a change fails pass `00` or `01` — misplaced or duplicated code makes
every later pass moot. Each file also carries a "Project mode" note for tree-wide sweeps and can
be run standalone when you need only one lens.

1. [`references/00-structure-placement.md`](references/00-structure-placement.md) — package
   placement (`core/packages`/`contrib`), acyclic layering (import-linter), facade discipline,
   new-package wiring.
2. [`references/01-canonical-reuse.md`](references/01-canonical-reuse.md) — did the code
   reimplement a concern an existing core package (or stdlib) already owns? *(blocker class)*
3. [`references/02-principles.md`](references/02-principles.md) — typed/minimal APIs, errors &
   resilience, async concurrency, composition, currency, AI/model features.
4. [`references/03-security-privacy.md`](references/03-security-privacy.md) — trust-boundary
   validation, injection safety, token hygiene, crypto, data minimization.
5. [`references/04-quality.md`](references/04-quality.md) — root-cause over patches, dead code,
   maintainability, style gates.
6. [`references/05-tests-tdd.md`](references/05-tests-tdd.md) — TDD, determinism (async, parallel,
   random order), injected clocks and env/fs discipline, fixtures.
7. [`references/06-docs-supply-chain.md`](references/06-docs-supply-chain.md) — docstrings,
   Conventional Commits, `uv.lock`, `pip-audit`, SHA-pinned actions, SBOM/provenance.
8. [`references/07-comments-docstrings.md`](references/07-comments-docstrings.md) — comments and
   docstrings describe the code as it is, not plans/history/process.

## Severity and finding format

```
severity (blocker / should-fix / nit) — file:line — what's wrong — which principle — suggested fix
```

- **blocker** — hard-principle violation (upward/cyclic import, concern reimplemented, bare
  `raise`/swallowed error on a fallible runtime path, unbounded queue / `asyncio` task with no
  cancellation, global mutable registry / import-time side effect, trust boundary not validated,
  `Any` on a public surface, behavioral change with no test). Fix before merge.
- **should-fix** — real defect or debt that isn't a baseline violation (compat shim, wall-clock
  sleep in a test, inline config instead of a fixture, reinvented stdlib facility, one large module
  that should be split by concern).
- **nit** — minor/style, take-it-or-leave-it.

## Validation is via make (see the `validate` skill)

**Scope every command to the changed package(s)** — the full-workspace gates are slow across 40+
packages and belong to a project audit or CI sign-off, not a per-change review:

```bash
make fmt-check                       # fast, whole-tree formatting check
make lint P=<pkg>                    # ruff, scoped to the package
make typecheck P=<pkg>               # mypy strict, scoped
make test P=<pkg> T=<pattern>        # scoped tests
make test-affected                   # only packages the diff touches
uv run import-linter                 # cheap layering guard
make check                           # full canonical gate — audit/CI sign-off
uv run pip-audit                     # dependency vulnerability scan
```

Treat a green run as **necessary but not sufficient**: it does not catch unbounded concurrency,
missing timeouts/cancellation, `asyncio` task leaks, global-registry composition smells, duplicated
owners, or boundary-validation gaps. Those are on the reviewer.

# Python Review — Plan, Clarify, Apply

An alternative orchestrator to [`review-changes.md`](./review-changes.md) /
[`review-project.md`](./review-project.md): instead of sequencing the 00–07 lenses, it fans the
review out into **parallel subagent passes by Python concern**, then plans and applies fixes. Use
it when you want one driver to take a change from review through to merged fixes.

Run each pass as a **separate subagent with clean context**. The orchestrator (this file)
sequences them and collects findings. Do not concatenate passes into one prompt.

Mode is either **changes** (a diff: branch, commit range, `HEAD~1`) or **project** (whole tree,
no diff). State the mode up front.

> The focused 00–07 files hold the canonical, pykit-specific checks (placement, canonical-owner
> reuse, security/privacy, supply chain, comments/docstrings). This file is the *driver*; when a
> pass below needs the full rule for a lens, defer to the matching focused file rather than
> duplicating it.

---

## Phase 1 — Scope

1. `git status`, `git diff --stat`, `git diff` (changes mode) or list the package tree +
   dependency map (project mode). Preserve uncommitted changes; integrate on top, never discard.
2. List the surface to review: changed packages/domains (changes mode) or chosen packages/
   workspace (project mode). Note cross-cutting touches: a core package's public surface fans out
   to the root `pykit` facade, contrib adapters, and downstream/sibling parity (rskit reference;
   see `docs/parity-matrix.md`). Also flag root `pyproject.toml`, `uv.lock`, `domains.toml`,
   import-linter config, shared error types (`AppError`), and public re-exports.
3. Determine which passes apply via the triggers below. Skip non-applicable passes explicitly in
   the final report.

The reviewer judges code as written, against the rules below and the baseline in
[`.github/copilot-instructions.md`](../../../copilot-instructions.md). PR descriptions, commit
messages, or plan/ADR docs are scope hints only — never justifications.

## Phase 2 — Passes

Run **A first** (cheap, gates the rest). Then **B–F in parallel** where independent. Then **G
last** (cross-references everything).

Each subagent receives: its scope, the pass spec below, and nothing else. Scope `uv`/`make` to
the touched package(s) with `P=<package>` or to the touched domain with `make check-<domain>`;
the unscoped workspace gates are slow across every package and belong to sign-off/CI.

### Pass A — Mechanical (always runs)

Tool output only, no judgment. Use pykit's real gates:

```bash
make fmt-check P=<package>              # ruff format --check, scoped
make lint P=<package>                   # ruff check, scoped
make typecheck P=<package>              # mypy strict, scoped
make test P=<package> T=<pattern>       # pytest, optionally narrowed by -k pattern
make check-<domain>                     # fmt/lint/typecheck/test for the touched domain
uv run import-linter                    # layer architecture, if imports/domain changed
uv run pip-audit                        # if deps/public security surface changed
```

Report pass/fail per command with the first failure block verbatim.

### Pass B — Correctness

**Scope:** all in-scope `.py` files.

Check: broad `Any` / untyped `object` / unchecked `cast()` leaking onto public surfaces; bare
`raise` used outside an active exception or re-raises that lose cause instead of `raise ... from
e`; `except Exception: pass` / swallowed errors / success-shaped fallbacks masking failure; mutable
default arguments; resource cleanup on every return path (`with` / `async with` / `try/finally`);
`AppError` typed code and cause preserved; pydantic v2 models and typed enums where they are the
right public contract; `mypy --strict` clean. *(Canonical owner: pass [`01`](./01-canonical-reuse.md).)*

Skip if: scope is docs-only or config-only.

### Pass C — Async and concurrency

**Scope:** files with `async def`, `asyncio`, `anyio`, `create_task`, queues, locks, semaphores,
thread/process pools, or streaming iterators.

Check: every spawned task has clear ownership, cancellation, timeout, and shutdown — a
fire-and-forget `asyncio.create_task()` with no retained handle and cancellation path is a
**blocker**; no lock held across blocking/network calls unless justified; shared state guarded or
confined to one task; structured concurrency (`asyncio.TaskGroup` / anyio task groups) over loose
tasks; queues/buffers/semaphores are **bounded with documented backpressure** and components
**drain in-flight work on shutdown**; cancellation is observed and not swallowed; time-dependent
paths are testable via an **injected clock/time provider**, not wall-clock sleeps.

Skip if: no async/concurrency surface in scope.

### Pass D — Composition and lifecycle

**Scope:** registries, `Component` impls, DI/bootstrap wiring, provider/adapter construction,
entry points, anything wiring dependencies together.

Check: registries and policies are **explicitly injected**, selection is config-driven; **no
import-time side effects, no mutable module-level registry**, no reaching for a global logger/
tracer — inject them (a module-level dict registry mutated at runtime, or import-time code that
dials network / reads env / registers into a global, is a **blocker**); lifecycle (`start`/
`stop`/`health`) honored with registry ordering and drain-on-stop; adapters register through
explicit registration functions and live in `contrib/pykit-<name>/`, not wired unconditionally
into core defaults. *(Placement: pass [`00`](./00-structure-placement.md); composition principle:
pass [`02`](./02-principles.md).)*

Skip if: no composition/lifecycle/registry surface in scope.

### Pass E — Security, config, and boundaries

**Scope:** external-facing surfaces (HTTP, process, storage/database/cache adapters, auth,
crypto), config loaders, env-var handling, path handling, and docs describing config or env.

Check: untrusted input validated at every trust boundary before flowing into a query, path,
command, deserialization, or model output consumer (an unvalidated path is a **blocker**);
parameterized queries only — never f-string/concatenated SQL; argv-only subprocess with
`shell=False`, never `shell=True` with untrusted input; tokens/credentials in headers not query
strings, never logged, redacted in errors; auth header-only, reject query-string tokens, JWT alg
allow-list + reject `alg: none` + require `exp`/`iss`/`aud`; current crypto only (no MD5/SHA-1-for-
security/ECB/static-IV/hard-coded key) routed through `pykit-encryption`/`pykit-security`;
untrusted reads have explicit limits. *(Full rule: pass [`03`](./03-security-privacy.md).)*

Skip if: no security-sensitive, config, env, or path code in scope.

### Pass F — API surface and dependencies

**Scope:** package public surfaces, `__init__.py`, pyproject metadata, optional extras, anything
changing exported items.

Check: new public items intentional (unexport private helpers with leading underscore and avoid
unnecessary re-exports through the root `pykit` facade); no broad `Any` / untyped `object` escape
hatch on a public surface except documented genuinely-opaque values; PEP 695 generics / Protocols
over ad-hoc ABCs or untyped dicts; new deps justified (maintained, no open CVE, not duplicating an
owning package or the stdlib — currency, pass [`01`](./01-canonical-reuse.md)); `pyproject.toml`
and `uv.lock` updated together; a new package wired into the core or contrib workspace,
`domains.toml`, import-linter contracts, and the matching `make check-<domain>`, with a package
`__init__.py` overview/docstring.

Skip if: no public items, deps, or `pyproject.toml` in scope.

### Pass G — Tests, docs, semantics (runs last)

**Scope:** the in-scope code plus findings from A–F.

Check: behavioral code in scope has tests covering it (changes mode: in the same diff; project
mode: anywhere in the tree); bug fixes have a regression test that fails without the fix; failure
paths asserted, not just happy paths; tests are deterministic under configured pytest parallel/
random-order tooling (`pytest -n auto` and `pytest-randomly` if present) and depend on no wall
clock, network, or working directory unless intentional (time uses an **injected clock**; env-var
tests use `monkeypatch`; filesystem tests use `tmp_path`); coverage meets pykit's 60% minimum via
`make test-coverage`; parsers/validators/auth/JWT/codecs/schema have fuzz/property tests where
appropriate; fixtures over large inline config; an operation does what its name implies; every
public item has a Google-style docstring that **matches implemented behavior**, each package has a
package docstring / `__init__.py` overview; comments describe the code as it is, not plans/history.
*(Full rules: passes [`05`](./05-tests-tdd.md) and [`06`](./06-docs-supply-chain.md); comment
hygiene: pass [`07`](./07-comments-docstrings.md).)*

Always runs.

## Phase 3 — Consolidate

Orchestrator collects findings into one table:

```text
pass | severity (blocker/should-fix/nit) | file:line | finding | suggested fix
```

Severity rule: **blocker** = principle violation, behavior is wrong, or a contract is broken
(see [`SKILL.md`](../SKILL.md) for the full definition). Otherwise should-fix or nit.

Group by file in the final report. State explicitly any pass that was **skipped** (with the
trigger that failed) and any pass that was **deferred** (with reason).

## Phase 4 — Plan and clarify

Group findings by pass, order by severity. For each group write a one-line fix plan: what
changes, where, how it's verified. Flag ambiguities (behavior change vs strict fix, breaking API
vs deprecation, doc-only vs behavior-aligning) with a proposed default and the alternative.
**Pause for user confirmation before editing.**

## Phase 5 — Apply

After confirmation:

1. Apply fixes in plan order, one pass per commit where reasonable (Conventional Commits:
   `feat`/`fix`/`docs`/`refactor`/`test`/`chore`).
2. Re-run the matching pass's validation after each fix, scoped to the touched package(s). Stop
   and report if anything fails.
3. Final step: re-run Pass A across the in-scope packages.

## Reviewer notes

- Code judges itself. External narrative (PR description, commit message, plan/ADR doc) is scope
  only, not justification.
- Detection commands (`rg`/`grep`, `uv`, `make`) are loaded by the subagent when it searches, not
  held in the resident prompt.
- If scope is trivial (docs-only, single-line fix), run only A and G; skip the rest with explicit
  reason.

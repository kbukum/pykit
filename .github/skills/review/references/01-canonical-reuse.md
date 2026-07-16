# Pass 01 — Canonical-owner reuse

pykit *is* the canonical Python toolkit, so the duplication risk is internal: **did the change
reimplement something an existing package (or the standard library) already owns?** Vibe-coded
code reaches for a fresh local helper instead of the owner — assume duplication until proven
otherwise. Treat findings here as a blocker class.

> **Run in a separate, clean-context agent** — never inline in the session that wrote the code.
> An independent reviewer re-derives every judgment from the code and the principles instead of
> trusting prior reasoning. A plan/spec may be passed in as a scope checklist only; it never
> excuses a baseline violation.

**Scope note.** *Changes mode:* for each new type/helper in the diff, name the concern and find
its owner. *Project mode:* sweep the tree for the patterns below and reconcile each against the
owning package — long-lived internal forks are exactly what this pass exists to surface.

## The rule

Reuse or enhance the canonical owner before writing new code. Never duplicate a shared concern
— **errors, config, logging, auth, retries/resilience, observability, HTTP, registries,
validation, process, di**. If the owner is inadequate, enhance it *generically* rather than
forking a copy in another package. pykit must stay foundational and multi-purpose: a fix belongs
in the owner so every consumer benefits.

## How to check — build the owner map, then reconcile

Do not eyeball it and do not rely on a fixed concern list — that is how a fork slips through.
Work it as a method, in order:

**1. Build the owner map.** Every pykit package is a potential owner. Establish what this package
*could* reuse before judging what it *does*:

```bash
find core/packages contrib -maxdepth 2 -name pyproject.toml | sort    # candidate owner set
uv run import-linter                                                   # allowed dependency edges
cat domains.toml                                                       # domain ownership
```

**2. Scan the package for every low-level operation and reconcile each against that map.** The
class most often missed is a **drop to the standard library for a capability a pykit package
already wraps** (safe paths, subprocess, HTTP, retries, registries, config) — not just a
reimplemented named concern. Sweep the in-scope code, not the tree:

```bash
rg -n 'pathlib\.|os\.|shutil\.|subprocess\.|httpx\.|requests\.|sqlite3\.|logging\.|print\(|time\.sleep|asyncio\.sleep|asyncio\.create_task|Exception\(|ValueError\(' <package> -g '*.py'
```

For each hit and each new local helper, name the concern, find its owner in the map, and decide:

- **Filesystem / paths / file IO** → the canonical storage/util/process package as appropriate
  (path confinement, permissions, atomic writes, subprocess argv handling). Raw `Path`/`os` use is
  fine for simple local package internals, but path validation, untrusted paths, atomicity, and
  cross-package helpers are candidate forks — reconcile against the owner.
- **Errors** → `pykit-errors` (`AppError`, typed codes, cause via `raise ... from e`, mappings).
  A fresh sentinel exception or bespoke error hierarchy for a shared concern is a fork.
- **Resilience** → `pykit-resilience` (retry / timeout / circuit-break), not hand-rolled loops or
  scattered `asyncio.timeout` + bespoke backoff.
- **HTTP** → `pykit-httpclient` / `pykit-server`, not a raw `httpx.AsyncClient()` with bespoke
  retry/timeout policy on public paths.
- **Subprocess** → `pykit-process` (argv-only, bounded, observable), not bare `subprocess.run` in
  reusable library code.
- **Config / logging / di / observability** → the owning package; logging uses injected
  structured logger (`structlog` or std `logging`), never `print()` outside CLI/reporting code.
- **Validation / schema / serialization / crypto** → `pykit-validation`, `pykit-schema`,
  `pykit-encryption`, or `pykit-security` where the concern is shared. Use current stdlib or
  well-maintained libraries only when no pykit owner exists.

The list above is illustrative, not exhaustive: the rule is *any* package, so if a hit maps to a
pykit owner not named here, it still counts.

**3. Judge each candidate — reuse, enhance, add, or justify:**

- Owner covers it → **reuse**: delete the fork, call the owner. *(blocker)*
- Owner is close but inadequate → **enhance it generically** so every consumer benefits, then
  reuse — never fork a tweaked copy. "Almost the same" (a near-copy with one changed line, or a
  copied comment) is still a fork.
- No owner and the capability is genuinely foundational and generally useful → **add it to the
  owning package (or a new one)**, not locally — a local solution is a **should-fix** with an
  "upstream to the owner" note.
- Deliberately stricter/narrower policy that must not be shared → **justified local**: state why,
  and flag it as a candidate to promote into the owner.

An owner that **nothing imports yet** is a strong signal its intended consumers are running local
forks — check it explicitly:

```bash
rg -n 'from pykit_<owner>|import pykit_<owner>|from pykit\.<owner>|import pykit\.<owner>' core contrib -g '*.py'
```

## Output for this pass

Per finding, name the concrete package/symbol that should have been used (e.g. "use
`pykit_errors.AppError` instead of a local `ConfigError`", "use `pykit-resilience` retry policy
instead of a hand-rolled loop", "wrap with `pykit-process` rather than `subprocess.run`") and its
outcome (reuse / enhance / add / justified-local).

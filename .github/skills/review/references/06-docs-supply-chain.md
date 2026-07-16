# Pass 06 — Docs & supply chain

Docs drift and dependency risk are the quiet failures — the code works, so nobody notices the
stale docstring or the unvetted new dependency until much later. This pass keeps the published
surface honest and the dependency set clean.

> **Run in a separate, clean-context agent** — never inline in the session that wrote the code.
> An independent reviewer re-derives every judgment from the code and the principles instead of
> trusting prior reasoning. A plan/spec may be passed in as a scope checklist only; it never
> excuses a baseline violation.

**Scope note.** *Changes mode:* check the docs and deps the diff touches or invalidates.
*Project mode:* audit every package's docstrings, READMEs, `pyproject.toml`/`uv.lock`, and the CI/
release wiring for the invariants below.

## Docs

- **Public API documented.** Every public item has a Google-style docstring; every package has a
  package docstring / `__init__.py` overview. pykit publishes Python packages, so docstrings and
  rendered package docs are the public documentation — missing docs on new public API is a
  should-fix.
- **Docs match behavior.** A behavioral change updates the affected docstrings, package overview,
  README, and examples. Stale docs that now describe removed or changed behavior are a should-fix.
  (Docstring *accuracy* vs the code is pass `07`; this check is that docs were updated at all.)
- **Canonical docs regenerated.** A package rename/add/remove updates `domains.toml`, any generated
  package index, and `docs/parity-matrix.md` in the same change. A stale parity matrix or module
  index is a should-fix.
- **Examples run.** Example code / README snippets reflect the current API and are covered by tests
  when practical.

## Supply chain

- **New dep justified.** Each added dependency is necessary (stdlib or pykit owner does not already
  cover it — pass `01`), maintained (recent releases), license-compatible, and free of known
  advisories. An unjustified or unmaintained dependency is a should-fix; one with an open CVE is a
  blocker.
- **Vulnerability + license clean.** `uv run pip-audit` passes for the relevant workspace; license
  policy is checked where configured. New findings are triaged with a rationale, not silently
  ignored.
- **Locked workspaces.** `pyproject.toml` and the relevant `uv.lock` reflect exactly what is used;
  no leftover optional extras, phantom deps, or missing lock updates.
- **CI/release hygiene** (if touched). GitHub Actions pinned by commit SHA (never a moving tag);
  minimum job permissions; release artifacts signed (cosign) and SBOM/provenance produced. A
  workflow pinned to a tag or granting broad permissions is a should-fix.

## Detection starters

```bash
# public functions/classes likely needing docstrings (spot-check the hits)
rg -n '^(def|async def|class) [A-Za-z][A-Za-z0-9_]*' core/packages contrib -g '*.py' -g '!**/tests/**'
# package __init__ files / package overviews
find core/packages contrib -path '*/src/*/__init__.py' | sort
# actions pinned by tag rather than SHA
rg -n 'uses:' .github/workflows | grep -v '@[0-9a-f]\{40\}'
# package map / matrix touched when packages change?
git diff --name-only | grep -E 'domains.toml|MODULE-INDEX|parity-matrix|pyproject.toml|uv.lock'
```

## Validation gate

```bash
make fmt-check P=<package>
make lint P=<package>
make typecheck P=<package>
uv run pip-audit                         # dependency vulnerability scan, when deps changed
```

Docs updated alongside behavior, locked workspaces, and a clean vulnerability scan pass this gate.

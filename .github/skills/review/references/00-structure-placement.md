# Pass 00 — Structure and placement

Confirm every touched (or, in project mode, every existing) item lives in the right package,
workspace, and layer, and that the dependency direction stays acyclic. This is the first gate:
misplaced code makes every later pass moot, so reject on failure here before going further.

> **Run in a separate, clean-context agent** — never inline in the session that wrote the code.
> An independent reviewer re-derives every judgment from the code and the principles instead of
> trusting prior reasoning. A plan/spec may be passed in as a scope checklist only; it never
> excuses a baseline violation.

**Scope note.** *Changes mode:* check the packages the diff touches plus the blast radius — a
change to a core package's public surface fans out to the root `pykit` facade, contrib adapters,
and sibling parity. *Project mode:* sweep each package's imports and dependency edges; the
placement and acyclicity rules below are invariants for the whole toolkit.

## The layering invariant

Dependency direction is explicit and acyclic; lower layers never import higher. A cycle or an
upward import is a **blocker**, enforced by `import-linter` and the domain map in `domains.toml`.
The package layering (downward dep direction only):

```text
Foundation     errors, config, logging
Core           validation, encryption, util, version, media
Component      component, provider, resilience
Infrastructure di, bootstrap, pipeline, dag, observability
Adapters       database, cache, storage, kafka, httpclient
Server         server, grpc, sse
Security       auth, authz, security
Specialist     llm, stateful, worker, process, workload
Platform       discovery, testutil, metrics
Data           dataset, bench, triton
```

`domains.toml` groups packages into checkable domains. A domain may depend only on its declared
lower domains; same-layer imports need explicit justification in the import-linter contract.

## Package placement

pykit is a uv-workspace monorepo split by role and dependency weight:

| Kind | Location | Owns |
|------|----------|------|
| Core package | `core/packages/pykit-<name>/` | foundation, core contracts, default local/in-memory implementations |
| Root facade | `core/packages/pykit/` | lazy-loading public re-exports of sub-packages only |
| Contrib adapter | `contrib/pykit-<parent>-<backend>/` | opt-in backend and its SDK dependency |
| Package tests | `<package>/tests/` | tests for that package's public behavior |

Each package has its own `pyproject.toml`. The core and contrib workspaces have their own uv
workspace roots and locks; dependency changes update the relevant `uv.lock`.

## Checks

- **Package placement.** Foundation or contract code → `core/packages/pykit-<name>/`. Heavy SDK
  backend code → `contrib/pykit-<parent>-<backend>/` owning that dependency. A backend SDK pulled
  into a core package, or foundation behavior buried in contrib, is a structure violation
  (blocker).
- **Acyclic, downward-only edges.** No lower-layer package imports a higher one; no cycle. This is
  gated by `uv run import-linter` and `make check-<domain>`. An upward import is a blocker.
- **New package wiring.** Own `pyproject.toml`, added to the relevant uv workspace, `domains.toml`,
  import-linter contracts, and the matching `make check-<domain>` path. Missing any is a
  should-fix.
- **Package docstring present.** Every package has a package docstring / `__init__.py` overview
  describing the package's public purpose. Missing is a should-fix.
- **No misplaced concerns.** Each cross-cutting concern stays in its canonical package — e.g. gRPC
  status mapping belongs in `pykit-grpc`, not `pykit-errors`. (Reuse of those owners is pass `01`.)
- **Backend opt-in.** A contrib adapter registers via an explicit registration function, not an
  import-time side effect, and the core package keeps a lean in-memory/local default.

## Detection starters

These flag candidates, not verdicts — read each hit to judge intent.

```bash
# package and workspace inventory
find core/packages contrib -maxdepth 2 -name pyproject.toml | sort
# architecture/layering
uv run import-linter
cat domains.toml
# package __init__ files and package docstrings to inspect
find core/packages contrib -path '*/src/*/__init__.py' | sort
# import-time side effects / mutable registries (read each hit)
rg -n '^(REGISTRY|registry|_registry)\s*=|asyncio\.create_task\(|os\.environ\[|load_dotenv\(|requests\.|httpx\.' core contrib -g '*.py'
```

Then run `uv run import-linter` and `make check-<domain>` for the touched domain.

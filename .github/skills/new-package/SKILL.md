---
name: new-package
description: >-
    Scaffold a new package in the pykit uv-workspace monorepo the canonical way — decide
    core vs contrib, add the pyproject.toml, wire the workspace members/dev group and the facade,
    add a package docstring, register the layer in import-linter/domains.toml, and update the
    parity matrix. Use when adding a new capability, foundation package, or adapter to pykit, or
    when unsure whether new code belongs in core or contrib.
user-invocable: true
---

# Adding a package to pykit

pykit is a uv-workspace monorepo: foundation packages live under `core/packages/pykit-<name>/`,
adapter packages under `contrib/pykit-<name>/`, and the root `pykit` package is a lazy-loading
facade that re-exports every sub-package. Getting placement and wiring right up front avoids
layering violations and facade drift later.

## Step 1 — Decide: core or contrib

- **Shared foundation / cross-cutting capability** (errors, config, logging, provider, pipeline,
  resilience, di, auth, observability, …) → `core/packages/pykit-<name>/`.
- **Provider/adapter for an external system** (a cloud SDK, driver, broker client, ML runtime) →
  `contrib/pykit-<domain>-<name>/` (e.g. `pykit-storage-s3`, `pykit-messaging-kafka`). See the
  `new-backend` skill for the adapter specifics.

When in doubt between core and contrib, ask: does it pull a heavy external dependency? Heavy dep →
contrib; stdlib + pykit packages only → core.

## Step 2 — Pick the layer and confirm dependency direction

pykit layers depend **downward only** (enforced by import-linter; `uv run import-linter`). Consult
`domains.toml` for the domain→package map and each domain's `depends_on`:

- core → patterns → crosscutting → composition → transport → auth → {data, ai} → media → infra

Your new package may only import lower or same-layer packages. A lower layer importing a higher one
is a **blocker**. Transport (server/grpc/sse) specifically must not import auth/authz — depend on a
lower-layer Protocol and inject the implementation instead.

## Step 3 — Create the package layout

```
core/packages/pykit-<name>/
├── pyproject.toml
├── README.md
├── src/pykit_<name>/
│   └── __init__.py          # package docstring + public re-exports
└── tests/
```

`pyproject.toml` follows the sibling packages: `name = "pykit-<name>"`, `version` in lock-step with
the workspace, `license = { text = "MIT" }`, `requires-python = ">=3.13"`, `dependencies` listing
only the pykit-* packages it actually uses, hatchling build targeting `src/pykit_<name>`. The
`__init__.py` opens with a Google-style package docstring:

```python
"""pykit_<name> — <one-line responsibility>.

<2–3 lines on the model, invariants, and what it deliberately does not do.>
"""
```

Conventions from `.github/copilot-instructions.md`: typed, minimal public API (no `Any`); PEP 695
generics; Protocol-based design (not ABCs); frozen dataclasses / pydantic v2 for data; async-first;
typed `AppError` preserving cause; no `print()` in library code; no import-time side effects. Split
by focused modules (types, options, registry, adapter) — never pile unrelated logic into one file.

## Step 4 — Wire the workspace and facade

- The workspace picks the package up via the `members = ["packages/*"]` glob, but also add it to the
  `[dependency-groups] dev` list in `core/pyproject.toml` (or `contrib/pyproject.toml` members +
  dev group for an adapter).
- For a core capability consumers should reach through the facade, add it to the `pykit` facade:
  the `[project] dependencies` in `core/packages/pykit/pyproject.toml` and the `_SUBPACKAGES`
  lazy-load map in `core/packages/pykit/src/pykit/__init__.py`.
- Refresh the lockfile: `uv lock` (from the affected workspace root).

## Step 5 — Register the layer

Add the package (name without the `pykit-` prefix) to the correct `[domains.<domain>].modules` list
in `domains.toml` so the `make check-<domain>` gates and generated docs pick it up, and add/extend
the matching import-linter layer contract in `core/pyproject.toml` so its dependency direction is
enforced.

## Step 6 — Parity matrix

If this capability exists (or should be tracked) in rskit, add/adjust its row in
`docs/parity-matrix.md` (✅ present · ➖ absent · ⏳ planned) with a short note. See the
`parity` skill for the capability-not-blind mirroring policy.

## Step 7 — Validate

```bash
make fmt
make build     P=pykit-<name>
make lint      P=pykit-<name>
make typecheck P=pykit-<name>
make test      P=pykit-<name>
uv run import-linter
```

## Checklist

- [ ] Placement decided (core / contrib) and justified by real deps
- [ ] Layer confirmed; imports only go downward (`import-linter` clean)
- [ ] Package docstring present; files split by concern
- [ ] Public API typed/generic (Protocols, PEP 695), no `Any`; data via dataclass/pydantic
- [ ] Added to the right workspace `dev` group; facade wired (deps + `_SUBPACKAGES`) if core
- [ ] `domains.toml` + import-linter contract updated; `uv.lock` refreshed
- [ ] `docs/parity-matrix.md` updated if it has a cross-kit counterpart
- [ ] build/lint/typecheck/test green for the package

Per repo workflow, **create the branch and make edits only** — the maintainer commits and pushes.

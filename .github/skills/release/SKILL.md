---
name: release
description: >-
    Cut a release of the pykit uv-workspace monorepo — decide the semver bump, update the
    CHANGELOG, apply the lock-step version bump across every package, run the full pre-release
    gates and supply-chain sweep, tag, and publish to PyPI via Trusted Publishing. Use when
    preparing or publishing a pykit release or checking release readiness.
user-invocable: true
---

# Releasing pykit

pykit is a uv-workspace monorepo (`core/packages/`, `contrib/`). All packages currently share a
single **lock-step** version and publish to PyPI via **Trusted Publishing** (no API tokens in CI).
Full details live in [`docs/RELEASING.md`](../../../docs/RELEASING.md),
[`docs/VERSIONING.md`](../../../docs/VERSIONING.md), [`docs/policy/SEMVER.md`](../../../docs/policy/SEMVER.md),
and [`docs/policy/DEPRECATION.md`](../../../docs/policy/DEPRECATION.md).

## Prerequisites

- Listed in `MAINTAINERS.md` with push access to `kbukum/pykit`.
- On `main`, clean working tree. `git`, `gh`, and `uv` on `$PATH`; commits GPG-signed
  (`git config commit.gpgsign true`) so the release tag can be signed.
- Trusted Publishing to PyPI configured for the repository.

## Step 1 — Full pre-release gate

A release is the one time to run the **complete** gates rather than the affected set:

```bash
make check                  # fmt-check + lint + typecheck + test (whole workspace)
make test-coverage          # coverage gate (minimum 60%)
uv run import-linter        # layer architecture compliance
uv run pip-audit            # dependency vulnerability scan
```

Also run the `review` project audit in a fresh agent before a release. Treat green gates as
necessary but not sufficient.

## Step 2 — Decide the version

```bash
git tag --sort=-v:refname | head -1
git log --oneline $(git describe --tags --abbrev=0)..HEAD
```

Use [`docs/policy/SEMVER.md`](../../../docs/policy/SEMVER.md) (PEP 440 aware). While in `0.x`: a
breaking change in the `[Unreleased]` CHANGELOG section bumps **MINOR**; otherwise **PATCH**.

## Step 3 — Update the CHANGELOG

1. Open `CHANGELOG.md`.
2. Replace `## [Unreleased]` with `## [vX.Y.Z] - YYYY-MM-DD`.
3. Add a fresh empty `## [Unreleased]` section above it.
4. If the new `[vX.Y.Z]` section is empty, **refuse to release** — nothing to ship. (CI also
   refuses to tag when `[vX.Y.Z]` is missing from the file.)
5. Update the link references at the bottom if present.

## Step 4 — Bump versions (lock-step) and refresh the lock

All packages bump together. Use the helper, never hand-edit each manifest:

```bash
uv run scripts/bump-version.py vX.Y.Z        # root + every core/contrib pyproject.toml
uv lock                                       # refresh the lockfile
```

If the helper is unavailable, set `[project] version` to `X.Y.Z` in the root `pyproject.toml` and
every `core/packages/pykit-*/pyproject.toml` and `contrib/pykit-*/pyproject.toml`, then `uv lock`.

## Step 5 — Tag and publish

The maintainer commits the prepared edits, then tags and pushes:

```bash
git add pyproject.toml core/packages/*/pyproject.toml contrib/pykit-*/pyproject.toml uv.lock CHANGELOG.md
git commit -S -m "chore: prepare vX.Y.Z release"
git tag -s -a vX.Y.Z -m "vX.Y.Z"
git push origin main vX.Y.Z
```

Publishing runs in CI via Trusted Publishing on the tag (with SBOM/provenance) — follow the
remaining steps in [`docs/RELEASING.md`](../../../docs/RELEASING.md) (GitHub release with notes from
the CHANGELOG section, signed artifacts). CI actions must be SHA-pinned.

## Guardrails

- **Never** run destructive git commands (`reset --hard`, `checkout -- .`, `clean`) on uncommitted
  work without explicit permission.
- Per repo workflow, the agent prepares the branch/CHANGELOG/bump edits; **the maintainer commits,
  pushes the tag, and runs the actual publish** unless explicitly asked otherwise. Open a PR only
  when explicitly requested, following the PR template.
- Reference other-repo items with full URLs, never bare `#123`.

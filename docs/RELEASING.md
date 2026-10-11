# Releasing

Prepare and verify a release using the [versioning](VERSIONING.md), [SemVer](policy/SEMVER.md), and [deprecation](policy/DEPRECATION.md) policies. Publication requires maintainer authorization, signed tags, and configured PyPI Trusted Publishing.

## Prepare

Start from a clean release branch. Verify current tags, package versions, and changes since the intended baseline; use a minor bump for pre-1.0 breaking changes and a patch otherwise.

Run the full acceptance gates and a project review:

```sh
make check
make test-coverage
uv run --project core lint-imports --config core/pyproject.toml
uv run --project contrib lint-imports --config contrib/pyproject.toml
uv run --project core pip-audit
uv run --project contrib pip-audit
```

Confirm measured coverage meets package and overall policy; a report alone does not prove the thresholds.

Update the affected package manifests under `core/packages/` and `contrib/`. There is no root Python project or version-bump helper. For a lock-step train, update all published packages consistently.

```sh
uv lock --project core
uv lock --project contrib
uv lock --project core --check
uv lock --project contrib --check
```

Move the populated changelog body into a dated version section and retain a fresh `[Unreleased]`. Keep notes high-level and identify breaking changes. Do not release an empty change set.

## Publish

Review and commit only the prepared manifests, owning lockfiles, and changelog. Tag the approved commit with a signed workspace tag (`vX.Y.Z`) or package tag (`pykit-<name>/vX.Y.Z`), then push only the authorized refs.

The [release workflow](../.github/workflows/release.yml) builds core/contrib distributions selected by the tag, publishes through PyPI Trusted Publishing, attests distribution provenance, and creates a GitHub Release with distributions and a CycloneDX SBOM.

The workflow does **not** run the full acceptance suite or enforce changelog completeness. Finish those checks before publication. Its workspace build loops cover `core/packages/` and `contrib/pykit-*`; verify the intended artifact set in the build job before approving a train.

## Verify

Check the workflow for the exact tag and commit. Confirm every expected distribution, registry version, GitHub asset, SBOM, and attestation. Install the released packages in a fresh environment:

```sh
uv pip install --refresh "pykit==X.Y.Z" "pykit-errors==X.Y.Z"
```

For prereleases, ensure the manifest's PEP 440 version matches the tag's intended release. Build/upload tools normalize Python versions; the workflow does not bump manifests from a tag.

For hotfixes, create a branch from the intended historical release and use the same gates. Never move published tags or replace immutable registry versions; recover with a forward-fix release.

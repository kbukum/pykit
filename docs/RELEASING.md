# Releasing

The mechanical steps to cut a release of `pykit`. For *what* counts as a
breaking change vs a feature vs a fix, see [`policy/SEMVER.md`](policy/SEMVER.md)
and [`policy/DEPRECATION.md`](policy/DEPRECATION.md).

## Prerequisites

- You are listed in `MAINTAINERS.md` and have push access to `kbukum/pykit`.
- Your local clone is on `main` with no uncommitted changes.
- `git`, `gh`, and `uv` are on your `$PATH`.
- Your commits are GPG-signed (`git config commit.gpgsign true`) — release
  tags must be signed.
- Trusted Publishing to PyPI is configured for the repository (no API tokens
  in CI).

## 1. Decide the version

```sh
# What's the latest tag?
git tag --sort=-v:refname | head -1

# What changed since then?
git log --oneline $(git describe --tags --abbrev=0)..HEAD
```

Use the [SEMVER policy](./policy/SEMVER.md) to pick the next version. While
in `0.x`, every release with a breaking change in the `[Unreleased]`
CHANGELOG section bumps MINOR; otherwise PATCH.

## 2. Update the CHANGELOG

1. Open `CHANGELOG.md`.
2. Replace `## [Unreleased]` with `## [vX.Y.Z] - YYYY-MM-DD`.
3. Add a fresh empty `## [Unreleased]` section above it.
4. If `[Unreleased]` is empty, refuse to release — there is nothing to ship.
5. Update the link reference at the bottom of the file (if present).

CI refuses to tag if `[Unreleased]` is the only populated section, or if
`[vX.Y.Z]` for the version you're cutting doesn't exist in the file.

## 3. Bump versions across the workspace

All packages in pykit currently share a single version (lock-step). Update
the version in:

- Root `pyproject.toml` (`[project] version`)
- Every `packages/pykit-*/pyproject.toml` (`[project] version`)

A helper is provided:

```sh
uv run scripts/bump-version.py vX.Y.Z
```

Then refresh the lockfile:

```sh
uv lock
git add pyproject.toml packages/*/pyproject.toml uv.lock CHANGELOG.md
git commit -S -m "chore: prepare vX.Y.Z release"
```

## 4. Tag the release

```sh
git tag -s -a vX.Y.Z -m "vX.Y.Z"
git push origin main vX.Y.Z
```

The release workflow (`.github/workflows/release.yml`) is triggered by the
tag push and will:

- Build wheels and sdists for every `packages/pykit-*` and the facade.
- Run the full test suite + lint + type-check + `pip-audit`.
- Verify `uv lock --check` passes.
- Publish to PyPI via Trusted Publishing.
- Sign artifacts with [Sigstore](https://www.sigstore.dev/).
- Generate and attach a CycloneDX SBOM (`cyclonedx-py`).

## 5. Cut the GitHub Release

Once the workflow completes successfully, generate release notes from the
CHANGELOG and create the GitHub Release via `gh`:

```sh
./scripts/release-notes.sh vX.Y.Z > /tmp/notes.md
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file /tmp/notes.md \
  --verify-tag
```

Attach the Sigstore signature bundle and SBOM to the Release as assets if
the workflow did not already.

## 6. Verify on PyPI

```sh
uv pip install --refresh "pykit==X.Y.Z"
uv pip install --refresh "pykit-errors==X.Y.Z"
```

If a package fails to install, the release was not successful — investigate
the workflow logs.

## 7. Announce

- Post in the project's discussion / README "Latest" section.
- Open a "post-release smoke test" issue against the next sprint milestone.
- Notify sibling repos ([`gokit`](https://github.com/kbukum/gokit),
  [`rskit`](https://github.com/kbukum/rskit)) if any cross-sibling APIs
  changed.

## Hotfix releases

Hotfixes follow the same flow but skip the `[Unreleased]` rotation if the
fix is targeted at an older line:

```sh
git checkout v0.2.0
git checkout -b hotfix/v0.2.1
# … apply fix …
# add a `## [0.2.1] - YYYY-MM-DD` section to CHANGELOG.md
git tag -s -a v0.2.1 -m "v0.2.1"
git push origin v0.2.1
```

## Pre-releases

```sh
git tag -s -a v0.3.0-rc.1 -m "v0.3.0-rc.1"
git push origin v0.3.0-rc.1
gh release create v0.3.0-rc.1 --prerelease --title "v0.3.0-rc.1" \
  --notes-file /tmp/notes.md
```

Pre-releases bypass the CHANGELOG check (the `-rc.N` / `-beta.N` suffix is
detected by the release workflow).

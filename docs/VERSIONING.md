# Versioning Guide

This document explains how versioning works in the pykit workspace.

## Why versioning matters here

pykit is a **uv workspace** with one facade package (`pykit`) and 50+
sub-packages (`pykit-{name}`). Each package is published independently to
PyPI but currently all share the **same version** for predictability
during the `0.x` phase. The lock-step convention is convenience, not
contract — consumers should pin per package.

## Version Format

```
vMAJOR.MINOR.PATCH[-PRERELEASE][+BUILDMETADATA]
```

Examples:
- `v0.1.0` — first minor release
- `v1.0.0` — first major release
- `v1.2.3` — standard release
- `v1.0.0-rc.1` — release candidate
- `v1.0.0-beta.2` — beta

PEP 440 normalization is automatic when uploading to PyPI (e.g.,
`v0.3.0-rc.1` becomes `0.3.0rc1`).

## Tagging

A single Git tag covers the whole workspace:

```sh
git tag -s -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

The release workflow then publishes every `packages/pykit-*` and the
facade in lock-step.

## Bumping

A helper script bumps every `pyproject.toml` in the workspace:

```sh
uv run scripts/bump-version.py v0.2.0
```

Manual bumping is supported but error-prone — prefer the script.

## Compatibility Policy

### Pre-1.0 (`0.x.y`)

- **MINOR** (`0.X.0`) bumps **may** contain breaking API changes. Every
  break is documented in `CHANGELOG.md` under
  `### Changed (Breaking API Changes)`.
- **PATCH** (`0.x.Y`) bumps are bug fixes, performance improvements,
  internal refactors, and **non-breaking** additions.
- We will not promote a package to `1.0.0` until its public API is settled
  and we are willing to commit to the full `1.x` compatibility contract for
  at least 12 months.

### Post-1.0 (`1.x.y` and beyond)

See [`policy/SEMVER.md`](policy/SEMVER.md) for the full post-1.0 contract.

## Using Versioned Packages

```sh
# Use a specific version (lock-step)
uv add pykit==0.1.0
uv add pykit-errors==0.1.0
uv add pykit-resilience==0.1.0

# Or use the facade (re-exports everything)
uv add pykit==0.1.0
```

```python
from pykit.errors import AppError, ErrorCode
from pykit.resilience import CircuitBreaker
```

## Local Development

For local development across the workspace, `uv sync` automatically resolves
inter-package dependencies via path sources defined in `pyproject.toml`:

```toml
[tool.uv.sources]
pykit-errors = { workspace = true }
pykit-config = { workspace = true }
```

## Best Practices

1. **Always tag the workspace as a whole** until per-package versioning is
   formally adopted post-1.0.
2. **Follow SemVer strictly** — breaking changes = MAJOR (after 1.0) or
   MINOR (in 0.x).
3. **Update CHANGELOG.md** under `[Unreleased]` before tagging.
4. **Test before tagging** — run the full `uv run pytest` suite.
5. **Never force-push tags.**
6. **Use pre-release tags for testing** — `v0.2.0-beta.1`.

## References

- [PEP 440 — Version Identification](https://peps.python.org/pep-0440/)
- [Semantic Versioning](https://semver.org/)
- [uv workspaces](https://docs.astral.sh/uv/concepts/workspaces/)
- [policy/SEMVER.md](policy/SEMVER.md)
- [policy/DEPRECATION.md](policy/DEPRECATION.md)
- [RELEASING.md](RELEASING.md)

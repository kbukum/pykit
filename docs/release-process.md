# Release Process

## Versioning policy

pykit uses [SemVer](https://semver.org/) with a per-package tagging scheme:

| Scope | Tag pattern | Example |
|-------|-------------|---------|
| Single package | `{package-name}/v{X.Y.Z}` | `pykit-errors/v0.2.0` |
| Workspace-wide | `v{X.Y.Z}` | `v0.1.0` |

## PyPI Trusted Publishing (OIDC)

No API tokens are stored as secrets. Authentication uses OpenID Connect:

1. Go to [PyPI Trusted Publishing](https://pypi.org/manage/account/publishing/)
2. Add a publisher for each package:
   - Repository: `kbukum/pykit`
   - Workflow: `release.yml`
   - Environment: `pypi`

## How to cut a release

### Single package
```bash
git tag pykit-errors/v0.2.0
git push origin pykit-errors/v0.2.0
```

### Workspace-wide
```bash
git tag v0.2.0
git push origin v0.2.0
```

The GitHub Actions release workflow will build, publish to PyPI, generate an SBOM,
and create a GitHub release with notes auto-generated from merged PRs.

## Deprecation policy

Deprecated APIs receive `@deprecated` decorator + `DeprecationWarning` for 2 minor versions,
then are removed in the next major version.

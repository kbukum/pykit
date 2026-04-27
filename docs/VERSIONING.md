# Versioning

All packages in this monorepo start at `0.1.0`. Version bumps follow SemVer.

## Compatibility guarantees

- **Patch** (0.1.x): bug fixes only; no breaking changes
- **Minor** (0.x.0): new APIs; old APIs may be deprecated but not removed
- **Major** (x.0.0): breaking changes allowed; deprecations are removed

## Version management

Versions are managed in each package's `pyproject.toml`. There is intentionally
no "workspace-wide version" — packages evolve independently.

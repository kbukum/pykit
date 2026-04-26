# Semantic Versioning Policy

`pykit` follows [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)
with the workspace clarifications below.

## Versioning surface

`pykit` is a uv workspace with one facade package (`pykit`) and 50+
sub-packages (e.g. `pykit-errors`, `pykit-server`, `pykit-storage`). **Each
package is versioned independently**, even though we currently cut all
releases in lock-step. The lock-step practice is convenience, not contract —
consumers should pin per package.

## Pre-1.0 (`0.x.y`)

While the project is in `0.x.y`:

- **MINOR** (`0.X.0`) bumps **may** contain breaking API changes. Every break
  is documented in `CHANGELOG.md` under `### Changed (Breaking API Changes)`
  for the affected package.
- **PATCH** (`0.x.Y`) bumps are bug fixes, performance improvements, internal
  refactors, and **non-breaking** additions. PATCH releases never break the
  public API.
- We will not promote a package to `1.0.0` until its public API is settled
  and we are willing to commit to the full `1.x` compatibility contract for
  at least 12 months.

## Post-1.0 (`1.x.y` and beyond)

- **MAJOR** (`X.0.0`) — breaking change to a stable public API. Requires a
  deprecation cycle (see [`DEPRECATION.md`](DEPRECATION.md)) of at least one
  MINOR release before the breaking change ships.
- **MINOR** (`x.Y.0`) — backwards-compatible additions and behaviour changes.
  Marking an API as deprecated is a MINOR change.
- **PATCH** (`x.y.Z`) — backwards-compatible bug and security fixes only.

## What counts as the public API

For a Python package, the public API is every name reachable from the
package's `__init__.py` (and any submodule explicitly documented as public),
excluding names prefixed with `_`. Specifically:

- Public functions, classes, methods, constants, type aliases, and
  `Protocol` definitions.
- The signatures and observable behaviour of all of the above.
- Documented invariants in module/class/function docstrings.
- The set of supported Python versions (`requires-python`).
- The set of declared `Protocol` methods — adding a method to an exported
  Protocol is a break.

The following are explicitly **not** part of the public API and may change in
any release:

- Anything in a module starting with `_` (e.g., `pykit_x._internal`).
- Test helpers in `tests/` directories.
- Generated code (e.g., `*_pb2.py`, `*_pb2_grpc.py`) — when the upstream IDL
  changes.
- Dependency versions, beyond the documented minimum Python version.
- Private subclasses of public types.

## Workspace-level version skew

Sub-packages may temporarily be at different versions when a focused fix
ships (e.g. `pykit-storage 0.2.1` while the rest of the workspace stays at
`0.2.0`). The next workspace-level release brings everything back into
lock-step.

## Pre-release identifiers

Pre-releases use SemVer suffixes: `v0.3.0-rc.1`, `v0.3.0-beta.2`. Pre-release
tags do not require CHANGELOG entries but **must** be reproducible builds (no
moving Python interpreter reference, no floating action SHAs).

PEP 440 normalization is applied automatically by the build/upload pipeline:
`v0.3.0-rc.1` → `0.3.0rc1` on PyPI.

## See also

- [`DEPRECATION.md`](DEPRECATION.md) — how we deprecate and eventually
  remove APIs.
- [`../RELEASING.md`](../RELEASING.md) — the mechanical release process.
- [`../../GOVERNANCE.md`](../../GOVERNANCE.md) — who can cut a release and how.

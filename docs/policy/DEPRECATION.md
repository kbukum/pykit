# Deprecation Policy

This policy applies once a package reaches `1.0.0`. While in `0.x.y` we may
remove APIs in any MINOR release (see [`SEMVER.md`](SEMVER.md)), but we still
try to follow the spirit of this document where practical.

## Lifecycle of a deprecated API

```
   stable ──► deprecated ──► removed
              ↑           ↑
              MINOR       MAJOR
              release     release (≥ 1 MINOR later)
```

1. **Deprecation** — the API is marked deprecated in a MINOR release.
2. **Cohabitation** — the new and old APIs coexist for at least one full
   MINOR release cycle (target: 6 months of calendar time, minimum: 1 MINOR).
3. **Removal** — the deprecated API is removed in the next MAJOR release.

We never remove a deprecated API in a PATCH or MINOR release after `1.0.0`.

## How we mark deprecation

Every deprecated symbol carries:

1. A `@typing_extensions.deprecated(...)` decorator (PEP 702) — recognised
   by `mypy`, `pyright`, IDEs, and emitted as a runtime
   `DeprecationWarning`.
2. A `.. deprecated:: X.Y.Z` directive in the docstring (Sphinx-aware).
3. The replacement (or `no replacement, will be removed in vX.Y.Z`).

```python
from typing_extensions import deprecated

@deprecated("since v1.2.0; use pykit_auth.NewVerifier which threads context. "
            "Will be removed in v2.0.0.")
def new_auth_checker(cfg: Config) -> Checker:
    """Create an auth checker.

    .. deprecated:: 1.2.0
       Use :func:`pykit_auth.new_verifier` instead.
    """
    ...
```

4. A CHANGELOG entry under `### Deprecated` for the release that introduced
   the deprecation.
5. (Where helpful) a runtime `warnings.warn(..., DeprecationWarning,
   stacklevel=2)` from the package's first call, gated by a module-level
   `_warned: bool` flag, naming the replacement. This is optional — only
   do it for hot-path APIs where a docstring is easy to miss.

## What counts as a deprecation-eligible change

- Removing a function, method, class, constant, or type alias.
- Removing a field from a dataclass / Pydantic model (when the type is part
  of the public API).
- Adding a method to an exported `Protocol`.
- Tightening a parameter or return type.
- Changing observable runtime behaviour in a way callers might depend on.
- Removing a kwarg from a public function signature.

The following are **not** deprecations and may ship in a single MINOR/PATCH:

- Adding a new method to a class.
- Adding a new optional kwarg to a function.
- Adding a new field with a default to a dataclass / Pydantic model (only
  if the type is **not** required to be positionally constructed by callers).
- Tightening behaviour to fix a documented bug.

## Security exception

A vulnerability fix may break API in a PATCH release if no compatible fix
exists. This is the only exception. Such releases are flagged with
`SECURITY:` in the CHANGELOG and announced via GitHub Security Advisories.

## Deprecation checklist for maintainers

Before merging a deprecation PR:

- [ ] `@deprecated(...)` decorator on the symbol with version + replacement.
- [ ] `.. deprecated::` directive in the docstring.
- [ ] CHANGELOG `### Deprecated` entry under `[Unreleased]`.
- [ ] Replacement API exists and is documented.
- [ ] If the replacement requires a non-trivial migration, add a
      `## Migration` block to the CHANGELOG entry showing before/after.
- [ ] Removal date / version recorded in `docs/policy/DEPRECATIONS.csv`
      (sortable list — create on first deprecation).
- [ ] Test the deprecation path with `pytest.warns(DeprecationWarning)`.

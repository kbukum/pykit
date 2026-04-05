# pykit-authz

RBAC permission checking with wildcard pattern matching and gRPC status integration.

## Installation

```bash
pip install pykit-authz
# or
uv add pykit-authz
```

## Quick Start

```python
from pykit_authz import MapChecker, match_pattern, PermissionDeniedError

# Define roles with wildcard permission patterns
checker = MapChecker({
    "admin":  ["*"],                           # full access
    "editor": ["article:read", "article:write"],
    "viewer": ["*:read"],                      # read anything
})

checker.check("admin", "article:delete")   # True
checker.check("editor", "article:write")   # True
checker.check("viewer", "user:read")       # True
checker.check("viewer", "user:delete")     # False

# Pattern matching: resource:action with wildcards
match_pattern("article:*", "article:read")  # True
match_pattern("*:read", "user:read")        # True
```

## Key Components

- **Checker** — Runtime-checkable protocol defining `check(subject, permission, resource) -> bool`
- **MapChecker** — In-memory role→permissions checker with wildcard matching; supports `add_role()` and `remove_role()`
- **CheckerFunc** — Adapter wrapping any `Callable[[str, str, str], bool]` as a `Checker`
- **match_pattern()** — Match a permission against a wildcard pattern (`*`, `article:*`, `*:read`)
- **match_any()** — Returns `True` if any pattern in a list matches the required permission
- **PermissionDeniedError** — Extends `AppError` with `ErrorCode.FORBIDDEN` and maps to `grpc.StatusCode.PERMISSION_DENIED`

## Dependencies

- `pykit-errors` — Error handling with gRPC status mapping

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

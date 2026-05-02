# pykit-authz

Default-deny RBAC + ABAC authorization with wildcard matching and gRPC status integration.

## Installation

```bash
pip install pykit-authz
# or
uv add pykit-authz
```

## Quick Start

```python
from pykit_authz import AuthorizationEngine, AuthorizationRequest, Resource, RoleBinding, Subject

engine = AuthorizationEngine(
    roles=[
        RoleBinding("viewer", ("article:read",)),
        RoleBinding("editor", ("article:write",), inherits=("viewer",)),
        RoleBinding("admin", ("*",)),
    ]
)

request = AuthorizationRequest(
    subject=Subject("user-1", roles=("editor",)),
    action="write",
    resource=Resource("article", "article-1"),
)
assert engine.check(request)
```

## Key Components

- **AuthorizationEngine** — Canonical RBAC + ABAC engine with default-deny semantics
- **RoleBinding / ABACRule** — RBAC hierarchy and ABAC rule primitives
- **CheckerFunc** — Adapter wrapping any `Callable[[AuthorizationRequest], AuthorizationDecision | bool]` as a `Checker`
- **match_pattern()** — Match a permission against a wildcard pattern (`*`, `article:*`, `*:read`)
- **match_any()** — Returns `True` if any pattern in a list matches the required permission
- **PermissionDeniedError** — Extends `AppError` with `ErrorCode.FORBIDDEN` and maps to `grpc.StatusCode.PERMISSION_DENIED`

## Dependencies

- `pykit-errors` — Error handling with gRPC status mapping

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

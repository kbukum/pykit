# pykit-hook

Generic typed event hook system — subscribe, emit, and handle events asynchronously.

## Installation

```bash
pip install pykit-hook
```

## Quick start

```python
from pykit_hook import HookRegistry, hook

registry = HookRegistry()

@registry.on("user.created")
async def on_user_created(payload: dict) -> None:
    print(f"New user: {payload['email']}")

await registry.emit("user.created", {"email": "alice@example.com"})
```

## Features

- Typed event hooks with `Protocol`-based handler contracts
- Sync and async handler support
- Priority ordering and middleware for hook handlers
- Scoped registries for test isolation
- Zero external dependencies

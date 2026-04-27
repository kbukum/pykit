# pykit-tool

Tool definition, auto-wiring, registry, and middleware for agentic systems.

## Installation

```bash
pip install pykit-tool
```

## Quick start

```python
from pykit_tool import tool, ToolRegistry

registry = ToolRegistry()

@tool(registry=registry, description="Search the web for a query")
async def web_search(query: str) -> str:
    ...  # your implementation
    return "results"

# Execute tool by name (used by agents)
result = await registry.execute("web_search", {"query": "Python 3.13 features"})
```

## Features

- `@tool` decorator for type-safe tool definition with auto-generated JSON Schema
- Central `ToolRegistry` with name-based lookup and middleware support
- Auto-wires dependencies via `pykit-provider`
- Schema generation via `pykit-schema`
- Compatible with `pykit-agent` and `pykit-mcp`

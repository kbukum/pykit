# pykit-mcp

Bridge the pykit tool registry with the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/).

## Installation

```bash
pip install pykit-mcp
```

## Quick start

```python
from pykit_mcp import MCPServer
from pykit_tool import ToolRegistry

registry = ToolRegistry()

# Register tools with the registry, then expose via MCP
server = MCPServer(registry=registry)
await server.start()  # Exposes tools over MCP transport
```

## Features

- Auto-converts `pykit-tool` definitions to MCP tool descriptors
- JSON Schema generation via `pykit-schema` for tool input/output
- Supports stdio and SSE MCP transports
- Compatible with Claude Desktop, Cursor, and other MCP clients
- Async-first with lifecycle management

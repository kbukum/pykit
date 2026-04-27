# pykit-schema

JSON Schema generation from Python types and Pydantic models.

## Installation

```bash
pip install pykit-schema
```

## Quick start

```python
from pykit_schema import schema_for
from pydantic import BaseModel

class CreateUserRequest(BaseModel):
    name: str
    email: str
    age: int | None = None

schema = schema_for(CreateUserRequest)
print(schema)
# {'type': 'object', 'properties': {'name': {'type': 'string'}, ...}, ...}
```

## Features

- Derives JSON Schema from Pydantic v2 models and standard Python types
- Supports `TypedDict`, `dataclass`, and plain `Protocol` annotations
- Schema caching for performance in hot paths
- Used internally by `pykit-tool` and `pykit-mcp` for tool descriptor generation
- Zero additional runtime dependencies beyond Pydantic

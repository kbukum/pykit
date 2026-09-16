# pykit-schema

Generate and validate JSON Schema from Pydantic models, Python types, and function signatures.

## Installation

```bash
pip install pykit-schema
# or
uv add pykit-schema
```

## Quick start

```python
from pydantic import BaseModel
from pykit_schema import generate, validate

class CreateUserRequest(BaseModel):
    name: str
    email: str
    age: int | None = None

schema = generate(CreateUserRequest)
result = validate(schema, {"name": "Alice", "email": "alice@example.com"})

assert result.valid
```

## What it provides

- **`generate()`** builds JSON Schema 2020-12 from a Pydantic `BaseModel`.
- **`from_type()`** derives schema from a Python type such as `list[str]` or `dict[str, int]`.
- **`from_function()`** derives an input schema from a typed function signature and skips `self`, `cls`, `ctx`, and `context` parameters.
- **`validate()`** checks values against a schema and returns a `ValidationResult` with structured `ValidationError` entries.
- **`validate_structured_output()`** and **`validate_elicitation_schema()`** cover common model-output and MCP-style validation cases.

## Common patterns

```python
from pykit_schema import from_function, from_type

schema_for_tags = from_type(list[str], title="Tags")

async def search(ctx, query: str, max_results: int = 10) -> list[str]:
    return [query]

search_input_schema = from_function(search)
```

## Dependencies

- `pydantic>=2.12`
- `jsonschema>=4.23`

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)

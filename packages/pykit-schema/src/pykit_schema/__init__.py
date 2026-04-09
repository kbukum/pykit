"""pykit-schema — JSON Schema generation and validation from Python types.

Thin wrapper around Pydantic's ``model_json_schema()`` providing a
consistent API for generating JSON Schema 2020-12 documents from:

- Pydantic ``BaseModel`` subclasses (primary use case)
- Plain Python types via runtime model construction
- Function signatures via type hint introspection

Also provides ``validate()`` for validating values against JSON Schemas.

Usage::

    from pydantic import BaseModel
    from pykit_schema import generate, validate

    class SearchInput(BaseModel):
        query: str
        max_results: int = 10

    schema = generate(SearchInput)
    result = validate(schema, {"query": "hello", "max_results": 5})
    assert result.valid
"""

from pykit_schema.generate import (
    ValidationError,
    ValidationResult,
    from_function,
    from_type,
    generate,
    validate,
)

__all__ = [
    "ValidationError",
    "ValidationResult",
    "from_function",
    "from_type",
    "generate",
    "validate",
]

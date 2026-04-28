# pykit-validation

Chainable field validation and Pydantic model helpers with structured error accumulation.

## Installation

```bash
pip install pykit-validation
# or
uv add pykit-validation
```

## Quick Start

```python
from pykit_validation import Validator, FieldError, validate_model
from pydantic import BaseModel

# Chainable field validation
Validator() \
    .required("name", name) \
    .max_length("name", name, 100) \
    .min_length("password", password, 8) \
    .pattern("email", email, r"^[\w.+-]+@[\w-]+\.[\w.]+$") \
    .in_range("age", age, 0, 150) \
    .one_of("role", role, ["admin", "user", "viewer"]) \
    .custom(start < end, "end_date", "must be after start_date") \
    .validate()  # Raises InvalidInputError if any checks failed

# Pydantic model validation with pykit error conversion
class UserCreate(BaseModel):
    name: str
    email: str
    age: int

user = validate_model(UserCreate, {"name": "Alice", "email": "a@b.com", "age": 30})
# Raises InvalidInputError (not Pydantic ValidationError) on failure,
# with structured field details in err.details["fields"]
```

## Key Components

- **Validator** — Fluent chainable validator that accumulates `FieldError` instances and raises `InvalidInputError` on `validate()`
  - Built-in checks: `required`, `max_length`, `min_length`, `in_range`, `min_value`, `max_value`, `pattern`, `one_of`, `required_uuid`, `optional_uuid`, `email`, `url`, `before`, `after`, `custom`
- **FieldError** — Dataclass with `field` and `message` for individual validation failures
- **validate_model()** — Validate a dict against a Pydantic `BaseModel`, converting `ValidationError` to `InvalidInputError` with structured field details

## Dependencies

- `pykit-errors`
- `pydantic`

## See Also

- [Main pykit README](../../README.md)
- [tests/](tests/) — additional usage examples

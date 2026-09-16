# pykit-validation

Validate fields and Pydantic models with structured errors that map cleanly into pykit error handling.

## Installation

```bash
pip install pykit-validation
# or
uv add pykit-validation
```

## Quick start

```python
from pydantic import BaseModel
from pykit_validation import Validator, validate_model

Validator()     .required("name", name)     .max_length("name", name, 100)     .min_length("password", password, 8)     .pattern("email", email, r"^[\w.+-]+@[\w-]+\.[\w.]+$")     .in_range("age", age, 0, 150)     .one_of("role", role, ["admin", "user", "viewer"])     .custom(start < end, "end_date", "must be after start_date")     .validate()

class UserCreate(BaseModel):
    name: str
    email: str
    age: int

user = validate_model(UserCreate, {"name": "Alice", "email": "a@b.com", "age": 30})
```

## Core APIs

- **`Validator`** accumulates `FieldError` values and raises `InvalidInputError` on `validate()`.
- Built-in checks include `required`, `max_length`, `min_length`, `in_range`, `min_value`, `max_value`, `pattern`, `one_of`, `required_uuid`, `optional_uuid`, `email`, `url`, `before`, `after`, and `custom`.
- **`validate_model()`** validates a `dict` against a Pydantic `BaseModel` and converts `ValidationError` into `InvalidInputError` with structured field details.
- **`FieldError`** stores a single field name and message pair.

## Dependencies

- `pykit-errors`
- `pydantic`

## See also

- [Main pykit README](../../../README.md)
- [tests/](tests/)

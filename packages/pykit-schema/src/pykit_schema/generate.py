"""JSON Schema generation and validation from Python types.

Uses Pydantic's ``model_json_schema()`` under the hood, which produces
JSON Schema 2020-12 compliant documents. Also provides ``validate()``
for checking values against JSON Schemas.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, get_type_hints

import jsonschema
from pydantic import BaseModel, create_model

# Standard JSON Schema type alias.
type JSON = dict[str, Any]


@dataclass
class ValidationError:
    """A single validation error with a JSON path and message."""

    path: str
    message: str


@dataclass
class ValidationResult:
    """Result of validating a value against a JSON Schema."""

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)


def validate(schema: JSON, value: Any) -> ValidationResult:
    """Validate a value against a JSON Schema.

    Args:
        schema: A JSON Schema document as a dict.
        value: The value to validate.

    Returns:
        A ``ValidationResult`` with ``valid=True`` if the value matches
        the schema, or ``valid=False`` with a list of errors.

    Example::

        schema = {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
        result = validate(schema, {"name": "Alice"})
        assert result.valid
    """
    validator = jsonschema.Draft202012Validator(schema)
    errors = list(validator.iter_errors(value))

    if not errors:
        return ValidationResult(valid=True)

    validation_errors = [
        ValidationError(
            path=".".join(str(p) for p in err.absolute_path) or "$",
            message=err.message,
        )
        for err in errors
    ]
    return ValidationResult(valid=False, errors=validation_errors)


def generate(
    model: type[BaseModel],
    *,
    title: str | None = None,
    description: str | None = None,
    by_alias: bool = True,
    ref_template: str = "#/$defs/{model}",
) -> JSON:
    """Generate a JSON Schema from a Pydantic model.

    Args:
        model: A ``BaseModel`` subclass.
        title: Override the schema title.
        description: Override the schema description.
        by_alias: Use field aliases in the schema (default ``True``).
        ref_template: Template for ``$ref`` pointers.

    Returns:
        A JSON Schema document as a dict.

    Example::

        class SearchInput(BaseModel):
            query: str
            max_results: int = 10

        schema = generate(SearchInput)
    """
    schema = model.model_json_schema(by_alias=by_alias, ref_template=ref_template)

    if title is not None:
        schema["title"] = title
    if description is not None:
        schema["description"] = description

    return schema


def from_type(
    tp: type,
    *,
    title: str = "",
    description: str = "",
) -> JSON:
    """Generate a JSON Schema from a plain Python type.

    Creates a temporary Pydantic model with a single ``value`` field of the
    given type, then extracts the schema for that field. For ``BaseModel``
    subclasses, delegates to :func:`generate` directly.

    Args:
        tp: Any Python type (``str``, ``int``, ``list[str]``, etc.) or
            a ``BaseModel`` subclass.
        title: Optional schema title.
        description: Optional schema description.

    Returns:
        A JSON Schema document as a dict.

    Example::

        schema = from_type(list[str], title="Tags")
    """
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        return generate(tp, title=title or None, description=description or None)

    # Build a wrapper model to leverage Pydantic's schema generation.
    wrapper = create_model("_Wrapper", value=(tp, ...))
    full_schema = wrapper.model_json_schema()

    # Extract the schema for the 'value' field.
    props = full_schema.get("properties", {})
    schema: JSON = dict(props.get("value", {"type": "object"}))

    # Resolve $ref if the value property is a reference.
    if "$ref" in schema:
        ref_name = schema["$ref"].rsplit("/", 1)[-1]
        defs = full_schema.get("$defs", {})
        if ref_name in defs:
            schema = dict(defs[ref_name])

    if title:
        schema["title"] = title
    if description:
        schema["description"] = description

    return schema


def from_function(
    fn: Callable[..., Any],
    *,
    title: str = "",
    description: str = "",
) -> JSON:
    """Generate a JSON Schema from a function's signature.

    Inspects type hints on the function parameters to build a schema.
    Parameters without type hints are assumed to be ``Any``. Parameters
    named ``self``, ``cls``, ``ctx``, and ``context`` are excluded.
    Default values create optional fields.

    Args:
        fn: A callable with type-annotated parameters.
        title: Optional schema title.
        description: Optional schema description (defaults to function docstring).

    Returns:
        A JSON Schema document for the function's input parameters.

    Example::

        def search(query: str, max_results: int = 10) -> list[str]:
            ...

        schema = from_function(search)
    """
    skip = {"self", "cls", "ctx", "context", "return"}

    hints = get_type_hints(fn, include_extras=True)
    sig = inspect.signature(fn)

    fields: dict[str, Any] = {}
    for name, param in sig.parameters.items():
        if name in skip:
            continue

        annotation = hints.get(name, Any)

        if param.default is inspect.Parameter.empty:
            fields[name] = (annotation, ...)
        else:
            fields[name] = (annotation, param.default)

    model_title = title or getattr(fn, "__name__", "unknown")
    wrapper = create_model(model_title, **fields)
    schema: JSON = wrapper.model_json_schema()

    if title:
        schema["title"] = title
    if description:
        schema["description"] = description
    elif hasattr(fn, "__doc__") and fn.__doc__:
        first_line = fn.__doc__.strip().split("\n")[0].strip()
        if first_line:
            schema["description"] = first_line

    return schema

"""Pydantic model validation helpers."""

from __future__ import annotations

from pydantic import BaseModel, ValidationError

from pykit_errors import InvalidInputError


def validate_model[T: BaseModel](model_class: type[T], data: dict) -> T:
    """Create a Pydantic model from *data*, converting errors to *InvalidInputError*.

    Returns the validated model instance on success.
    Raises ``InvalidInputError`` with field details on failure.
    """
    try:
        return model_class.model_validate(data)
    except ValidationError as exc:
        fields = []
        messages = []
        for error in exc.errors():
            field_name = ".".join(str(loc) for loc in error["loc"])
            msg = error["msg"]
            fields.append({"field": field_name, "message": msg})
            messages.append(f"{field_name}: {msg}")

        err = InvalidInputError("; ".join(messages))
        err.details = {"fields": fields}
        raise err from exc

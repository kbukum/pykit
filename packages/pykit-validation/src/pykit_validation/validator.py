"""Chainable field validator mirroring gokit validation/."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pykit_errors import InvalidInputError


@dataclass
class FieldError:
    """A validation error for a specific field."""

    field: str
    message: str


class Validator:
    """Collects field validation errors with chainable methods.

    Usage::

        err = (
            Validator()
            .required("name", name)
            .max_length("name", name, 100)
            .min_length("password", password, 8)
            .validate()
        )
    """

    def __init__(self) -> None:
        self._errors: list[FieldError] = []

    # -- introspection ------------------------------------------------

    @property
    def has_errors(self) -> bool:
        return len(self._errors) > 0

    @property
    def errors(self) -> list[FieldError]:
        return list(self._errors)

    def add_error(self, field: str, message: str) -> None:
        self._errors.append(FieldError(field=field, message=message))

    # -- terminal -----------------------------------------------------

    def validate(self) -> None:
        """Raise *InvalidInputError* when errors have been collected."""
        if not self.has_errors:
            return

        messages = [f"{e.field}: {e.message}" for e in self._errors]
        err = InvalidInputError("; ".join(messages))
        err.details = {"fields": [{"field": e.field, "message": e.message} for e in self._errors]}
        raise err

    # -- chainable checks ---------------------------------------------

    def required(self, field: str, value: str) -> Validator:
        """Value must be a non-blank string."""
        if not isinstance(value, str) or value.strip() == "":
            self.add_error(field, "is required")
        return self

    def max_length(self, field: str, value: str, max_len: int) -> Validator:
        if len(value) > max_len:
            self.add_error(field, f"must be {max_len} characters or less")
        return self

    def min_length(self, field: str, value: str, min_len: int) -> Validator:
        if len(value) < min_len:
            self.add_error(field, f"must be at least {min_len} characters")
        return self

    def range_check(
        self, field: str, value: int | float, min_val: int | float, max_val: int | float
    ) -> Validator:
        if value < min_val or value > max_val:
            self.add_error(field, f"must be between {min_val} and {max_val}")
        return self

    def min_value(self, field: str, value: int | float, min_val: int | float) -> Validator:
        if value < min_val:
            self.add_error(field, f"must be at least {min_val}")
        return self

    def max_value(self, field: str, value: int | float, max_val: int | float) -> Validator:
        if value > max_val:
            self.add_error(field, f"must be {max_val} or less")
        return self

    def pattern(self, field: str, value: str, regex: str) -> Validator:
        """Value must match *regex*. Empty values are skipped (use ``required`` first)."""
        if value == "":
            return self
        if not re.search(regex, value):
            self.add_error(field, "does not match required format")
        return self

    def one_of(self, field: str, value: str, allowed: list[str]) -> Validator:
        """Value must be in *allowed*. Empty values are skipped."""
        if value == "":
            return self
        if value not in allowed:
            self.add_error(field, f"must be one of: {', '.join(allowed)}")
        return self

    def custom(self, condition: bool, field: str, message: str) -> Validator:
        """Add error when *condition* is ``False``."""
        if not condition:
            self.add_error(field, message)
        return self

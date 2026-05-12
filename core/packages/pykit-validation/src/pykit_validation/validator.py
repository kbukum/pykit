"""Chainable field validator with error accumulation."""

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

    def required(self, field: str, value: object) -> Validator:
        """Value must not be None, empty string, or empty collection."""
        if (
            value is None
            or (isinstance(value, str) and value.strip() == "")
            or (isinstance(value, (list, dict, set, tuple)) and len(value) == 0)
        ):
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

    def in_range(
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

    def required_uuid(self, field: str, value: str) -> Validator:
        """Value must be a non-empty valid UUID."""
        if value == "":
            self.add_error(field, "is required")
            return self
        import uuid as _uuid

        try:
            _uuid.UUID(value)
        except (ValueError, AttributeError):
            self.add_error(field, "must be a valid UUID")
        return self

    def optional_uuid(self, field: str, value: str | None) -> Validator:
        """Value must be a valid UUID if non-empty. Empty/None values pass."""
        if value is None or value == "":
            return self
        import uuid as _uuid

        try:
            _uuid.UUID(value)
        except (ValueError, AttributeError):
            self.add_error(field, "must be a valid UUID")
        return self

    def email(self, field: str, value: str) -> Validator:
        """Value must be a valid email address. Empty values are skipped."""
        if value == "":
            return self
        if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", value):
            self.add_error(field, "must be a valid email address")
        return self

    def url(self, field: str, value: str) -> Validator:
        """Value must be a valid HTTP or HTTPS URL. Empty values are skipped."""
        if value == "":
            return self
        if not value.startswith(("http://", "https://")):
            self.add_error(field, "must be a valid URL")
        return self

    def before(self, field: str, value: str, deadline: str) -> Validator:
        """Value (RFC 3339 datetime string) must be strictly before *deadline*."""
        if value == "":
            return self
        from datetime import datetime

        try:
            v = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            self.add_error(field, "must be a valid datetime")
            return self
        try:
            d = datetime.fromisoformat(deadline.replace("Z", "+00:00"))
        except ValueError:
            return self
        if v >= d:
            self.add_error(field, f"must be before {deadline}")
        return self

    def after(self, field: str, value: str, floor: str) -> Validator:
        """Value (RFC 3339 datetime string) must be strictly after *floor*."""
        if value == "":
            return self
        from datetime import datetime

        try:
            v = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            self.add_error(field, "must be a valid datetime")
            return self
        try:
            f = datetime.fromisoformat(floor.replace("Z", "+00:00"))
        except ValueError:
            return self
        if v <= f:
            self.add_error(field, f"must be after {floor}")
        return self

    def custom(self, condition: bool, field: str, message: str) -> Validator:
        """Add error when *condition* is ``False``."""
        if not condition:
            self.add_error(field, message)
        return self

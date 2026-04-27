"""Assertion helpers for pykit test suites."""
from __future__ import annotations

from typing import TypeVar

T = TypeVar("T")


def assert_ok(value: T | Exception) -> T:
    """Assert that value is not an exception and return it."""
    if isinstance(value, Exception):
        raise AssertionError(f"Expected Ok, got exception: {value!r}") from value
    return value  # type: ignore[return-value]


def assert_err(value: object, exc_type: type[Exception] = Exception) -> Exception:
    """Assert that value is an instance of exc_type."""
    if not isinstance(value, exc_type):
        raise AssertionError(f"Expected {exc_type.__name__}, got: {value!r}")
    return value


__all__ = ["assert_ok", "assert_err"]

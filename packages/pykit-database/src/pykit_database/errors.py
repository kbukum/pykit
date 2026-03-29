"""Translate SQLAlchemy errors into pykit-errors AppError subtypes."""

from __future__ import annotations

from sqlalchemy.exc import (
    IntegrityError,
    NoResultFound,
    OperationalError,
)

from pykit_errors import AppError, NotFoundError, ServiceUnavailableError


def is_connection_error(err: BaseException) -> bool:
    """Return ``True`` if *err* indicates a database connection failure."""
    return isinstance(err, OperationalError)


def is_not_found_error(err: BaseException) -> bool:
    """Return ``True`` if *err* indicates a missing row."""
    return isinstance(err, NoResultFound)


def is_duplicate_error(err: BaseException) -> bool:
    """Return ``True`` if *err* indicates a unique-constraint violation."""
    if isinstance(err, IntegrityError):
        msg = str(err).lower()
        return "unique" in msg or "duplicate" in msg
    return False


def translate_error(err: BaseException, resource: str = "") -> AppError:
    """Convert a SQLAlchemy exception into the corresponding :class:`AppError`.

    Falls back to a generic :class:`AppError` when no specific mapping exists.
    """
    if is_not_found_error(err):
        return NotFoundError(resource or "record")

    if is_connection_error(err):
        return ServiceUnavailableError(resource or "database", str(err))

    if is_duplicate_error(err):
        return AppError(f"duplicate {resource or 'record'}: {err}")

    return AppError(str(err))

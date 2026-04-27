"""RFC 9457 Problem Details for HTTP APIs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pykit_errors.base import AppError

_TYPE_BASE_URI = "https://pykit.dev/errors/"


def set_type_base_uri(uri: str) -> None:
    """Override the RFC 9457 type URI base.

    Args:
        uri: New base URI. Must end with '/'.

    Raises:
        ValueError: If *uri* does not end with '/'.
    """
    global _TYPE_BASE_URI
    if not uri.endswith("/"):
        raise ValueError(f"type base URI must end with '/': {uri!r}")
    _TYPE_BASE_URI = uri


def get_type_base_uri() -> str:
    """Return the current RFC 9457 type URI base."""
    return _TYPE_BASE_URI


def _code_to_kebab(code: str) -> str:
    """Convert an UPPER_SNAKE_CASE error code to kebab-case."""
    return code.lower().replace("_", "-")


def _code_to_title(code: str) -> str:
    """Convert an UPPER_SNAKE_CASE error code to title-cased human text.

    Examples:
        NOT_FOUND      → "Not Found"
        INTERNAL_ERROR → "Internal Error"
        INVALID_INPUT  → "Invalid Input"
    """
    return " ".join(word.capitalize() for word in code.split("_"))


@dataclass(frozen=True)
class ProblemDetail:
    """RFC 9457 Problem Details for HTTP APIs.

    Attributes:
        type: URI reference identifying the problem type.
        title: Short human-readable summary of the problem type.
        status: HTTP status code.
        detail: Human-readable explanation specific to this occurrence.
        code: Machine-readable application error code.
        retryable: Whether the client should retry the request.
        instance: URI reference identifying this specific occurrence.
        details: Extension members with additional context.
    """

    type: str
    title: str
    status: int
    detail: str
    code: str
    retryable: bool
    instance: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_app_error(cls, err: AppError, instance: str = "") -> ProblemDetail:
        """Create a ProblemDetail from an AppError.

        Args:
            err: The application error to convert.
            instance: Optional URI reference for this specific occurrence.

        Returns:
            A fully populated ProblemDetail.
        """
        code_str = err.code.value
        return cls(
            type=_TYPE_BASE_URI + _code_to_kebab(code_str),
            title=_code_to_title(code_str),
            status=err.http_status,
            detail=err.message,
            code=code_str,
            retryable=err.retryable,
            instance=instance,
            details=dict(err.details),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a flat RFC 9457 dict suitable for JSON responses.

        Omits *instance* when empty and *details* when empty.

        Returns:
            Dictionary with RFC 9457 members plus pykit extensions.
        """
        d: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "code": self.code,
            "retryable": self.retryable,
        }
        if self.instance:
            d["instance"] = self.instance
        if self.details:
            d["details"] = self.details
        return d


class ProblemDetailFactory:
    """Factory for creating ProblemDetail instances with a configurable type base URI.

    Prefer this over the module-level ``set_type_base_uri`` when running multiple
    services in a single process (e.g., tests, in-proc gateways).
    """

    def __init__(self, type_base_uri: str = "https://pykit.dev/errors/") -> None:
        if not type_base_uri.endswith("/"):
            raise ValueError(f"type base URI must end with '/': {type_base_uri!r}")
        self._type_base_uri = type_base_uri

    @property
    def type_base_uri(self) -> str:
        return self._type_base_uri

    def create(self, err: AppError, instance: str = "") -> ProblemDetail:
        """Create a ProblemDetail from an AppError using this factory's base URI."""
        code_str = err.code.value
        return ProblemDetail(
            type=self._type_base_uri + _code_to_kebab(code_str),
            title=_code_to_title(code_str),
            status=err.http_status,
            detail=err.message,
            code=code_str,
            retryable=err.retryable,
            instance=instance,
            details=dict(err.details),
        )

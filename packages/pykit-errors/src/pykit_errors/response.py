"""RFC 7807 Problem Details error response."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Self

from pykit_errors.base import AppError


@dataclass(frozen=True)
class ErrorResponse:
    """RFC 7807 Problem Details error response."""

    type: str
    title: str
    status: int
    detail: str
    instance: str = ""
    extensions: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_app_error(cls, err: AppError) -> Self:
        """Create an ErrorResponse from an AppError."""
        kebab = err.code.value.lower().replace("_", "-")
        return cls(
            type=f"https://pykit.dev/errors/{kebab}",
            title=err.code.value,
            status=err.http_status,
            detail=err.message,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary suitable for JSON responses."""
        d: dict[str, Any] = {
            "type": self.type,
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
        }
        if self.instance:
            d["instance"] = self.instance
        if self.extensions:
            d["extensions"] = self.extensions
        return d

"""Authorization error types."""

from __future__ import annotations

from pykit_errors import AppError
from pykit_errors.codes import ErrorCode


class PermissionDeniedError(AppError):
    """Permission denied — maps to gRPC PERMISSION_DENIED."""

    def __init__(self, subject: str, permission: str, reason: str = "default_deny") -> None:
        super().__init__(ErrorCode.FORBIDDEN, f"Permission denied: '{subject}' lacks '{permission}'")
        self.with_details({"subject": subject, "permission": permission, "reason": reason})

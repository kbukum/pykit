"""Authorization error types."""

from __future__ import annotations

import grpc

from pykit_errors import AppError


class PermissionDeniedError(AppError):
    """Permission denied — maps to gRPC PERMISSION_DENIED."""

    grpc_status = grpc.StatusCode.PERMISSION_DENIED

    def __init__(self, subject: str, permission: str) -> None:
        details = {"subject": subject, "permission": permission}
        super().__init__(
            f"Permission denied: '{subject}' lacks '{permission}'",
            details=details,
        )

"""Typed AI foundation errors."""

from __future__ import annotations

from pykit_ai.core import BudgetExceededReason


class GenAIError(Exception):
    """Base class for typed AI errors."""


class RateLimited(GenAIError):
    """Provider rate limit was exceeded."""


class ContextLengthExceeded(GenAIError):
    """Request exceeded the model context length."""


class ContentFilter(GenAIError):
    """Provider content filter blocked the request or response."""


class ModelOverloaded(GenAIError):
    """Provider reported transient capacity exhaustion."""


class BudgetExceeded(GenAIError):
    """A configured AI budget was exceeded."""

    def __init__(self, reason: BudgetExceededReason, message: str | None = None) -> None:
        self.reason = reason
        super().__init__(message or f"budget exceeded: {reason.value}")


class ModelNotFound(GenAIError):
    """Requested model was not found."""


class InvalidRequest(GenAIError):
    """Provider rejected an invalid request."""


__all__ = [
    "BudgetExceeded",
    "ContentFilter",
    "ContextLengthExceeded",
    "GenAIError",
    "InvalidRequest",
    "ModelNotFound",
    "ModelOverloaded",
    "RateLimited",
]

"""Typed inference errors."""

from __future__ import annotations


class InferenceError(RuntimeError):
    """Base class for inference adapter failures."""


class InferenceHTTPError(InferenceError):
    """Model-serving runtime returned an unsuccessful HTTP response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"inference runtime returned HTTP {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class InferenceAuthorizationError(InferenceError):
    """Prediction was denied by an injected authorization decider."""

"""Authentication protocols."""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from pykit_auth.jwt import Claims


class TokenValidator(Protocol):
    """Validates a token string and returns parsed claims."""

    def validate(self, token: str) -> Claims:
        """Validate *token* and return the parsed claims."""


class TokenGenerator(Protocol):
    """Generates a signed token from claims."""

    def generate(self, claims: Claims, expires_in: int | None = None) -> str:
        """Sign *claims* and return the encoded token string."""


class AuthMode(Enum):
    """Controls how authentication is enforced in middleware."""

    REQUIRED = "required"
    ACCEPT_MISSING = "accept_missing"
    BYPASS = "bypass"

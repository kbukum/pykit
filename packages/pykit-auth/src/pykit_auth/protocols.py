"""Authentication protocols mirroring gokit auth.TokenValidator / auth.TokenGenerator."""

from __future__ import annotations

from typing import Protocol


class TokenValidator(Protocol):
    """Validates a token string and returns parsed claims."""

    def validate(self, token: str) -> dict: ...


class TokenGenerator(Protocol):
    """Generates a signed token from claims."""

    def generate(self, claims: dict, expires_in: int | None = None) -> str: ...

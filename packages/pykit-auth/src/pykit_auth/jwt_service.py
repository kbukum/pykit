"""JWT token service mirroring gokit auth/jwt.Service."""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt

from pykit_errors import InvalidInputError


@dataclass
class JWTConfig:
    """Configuration for the JWT service."""

    secret: str
    algorithm: str = "HS256"
    issuer: str = ""
    audience: str = ""
    default_ttl: int = 3600


class JWTService:
    """JWT token generation and validation.

    Implements both ``TokenValidator`` and ``TokenGenerator`` protocols.
    """

    def __init__(self, config: JWTConfig) -> None:
        self._config = config

    # -- TokenGenerator --------------------------------------------------------

    def generate(self, claims: dict, expires_in: int | None = None) -> str:
        """Sign a JWT with standard registered claims."""
        now = int(time.time())
        ttl = expires_in if expires_in is not None else self._config.default_ttl

        payload: dict = {**claims, "iat": now, "exp": now + ttl}

        if self._config.issuer:
            payload.setdefault("iss", self._config.issuer)
        if self._config.audience:
            payload.setdefault("aud", self._config.audience)

        return jwt.encode(payload, self._config.secret, algorithm=self._config.algorithm)

    # -- TokenValidator --------------------------------------------------------

    def validate(self, token: str) -> dict:
        """Verify signature and decode a JWT, returning the claims dict.

        Raises ``InvalidInputError`` on any validation failure.
        """
        kwargs: dict = {"algorithms": [self._config.algorithm]}
        if self._config.issuer:
            kwargs["issuer"] = self._config.issuer
        if self._config.audience:
            kwargs["audience"] = self._config.audience

        try:
            return jwt.decode(token, self._config.secret, **kwargs)
        except jwt.PyJWTError as exc:
            raise InvalidInputError(f"invalid token: {exc}") from exc

    # -- Utility ---------------------------------------------------------------

    def decode_unverified(self, token: str) -> dict:
        """Decode a JWT **without** signature verification (debugging only)."""
        try:
            return jwt.decode(token, options={"verify_signature": False}, algorithms=[self._config.algorithm])
        except jwt.PyJWTError as exc:
            raise InvalidInputError(f"cannot decode token: {exc}") from exc

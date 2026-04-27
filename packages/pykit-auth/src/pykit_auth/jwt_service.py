"""JWT token service mirroring gokit auth/jwt.Service."""

from __future__ import annotations

import datetime
import time
from dataclasses import dataclass, field

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
    leeway_seconds: int = 60

    def __post_init__(self) -> None:
        if self.algorithm.startswith("HS") and len(self.secret.encode()) < 32:
            raise ValueError(
                f"HMAC secret must be at least 32 bytes for {self.algorithm}; "
                f"got {len(self.secret.encode())} bytes. "
                "Use a cryptographically random secret of at least 256 bits."
            )


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
            return jwt.decode(
                token,
                self._config.secret,
                leeway=datetime.timedelta(seconds=self._config.leeway_seconds),
                options={"require": ["exp", "iat"]},
                **kwargs,
            )
        except jwt.PyJWTError as exc:
            raise InvalidInputError(f"invalid token: {exc}") from exc

    # -- Utility ---------------------------------------------------------------

    def _decode_unverified(self, token: str) -> dict:
        """Decode a JWT **without** signature verification — DIAGNOSTIC USE ONLY."""
        try:
            return jwt.decode(token, options={"verify_signature": False}, algorithms=[self._config.algorithm])
        except jwt.PyJWTError as exc:
            raise InvalidInputError(f"cannot decode token: {exc}") from exc

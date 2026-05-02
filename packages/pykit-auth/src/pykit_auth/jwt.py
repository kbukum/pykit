"""JWT signing and verification with secure algorithm policy defaults."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from time import time

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed448, ed25519, rsa

from pykit_errors import InvalidInputError

type Claims = dict[str, object]
type VerificationKey = (
    rsa.RSAPublicKey
    | ec.EllipticCurvePublicKey
    | ed25519.Ed25519PublicKey
    | ed448.Ed448PublicKey
    | str
    | bytes
)


class JWTAlgorithm(StrEnum):
    """Supported JWT algorithms."""

    RS256 = "RS256"
    ES256 = "ES256"
    EDDSA = "EdDSA"
    HS256 = "HS256"


_ASYMMETRIC_ALGORITHMS = {JWTAlgorithm.RS256, JWTAlgorithm.ES256, JWTAlgorithm.EDDSA}
_REQUIRED_CLAIMS = ("exp", "iat", "nbf", "iss", "aud")


@dataclass(frozen=True, slots=True)
class JWTConfig:
    """Configuration for a JWT signer and verifier."""

    issuer: str
    audience: str
    algorithm: JWTAlgorithm = JWTAlgorithm.RS256
    private_key: str | bytes | None = None
    public_key: str | bytes | None = None
    shared_secret: str | bytes | None = None
    default_ttl: int = 3600
    leeway_seconds: int = 30
    allow_internal_hs256: bool = False
    key_id: str | None = None

    def __post_init__(self) -> None:
        if not self.issuer:
            raise ValueError("issuer is required")
        if not self.audience:
            raise ValueError("audience is required")
        if self.default_ttl <= 0:
            raise ValueError("default_ttl must be positive")
        if not 0 <= self.leeway_seconds <= 60:
            raise ValueError("leeway_seconds must be between 0 and 60")

        if self.algorithm is JWTAlgorithm.HS256:
            if not self.allow_internal_hs256:
                raise ValueError("HS256 is internal-only; set allow_internal_hs256=True explicitly")
            if self.private_key is not None or self.public_key is not None:
                raise ValueError("HS256 cannot be combined with asymmetric keys")
            secret = self._shared_secret_bytes()
            if len(secret) < 32:
                raise ValueError("HS256 shared_secret must be at least 32 bytes")
            return

        if self.shared_secret is not None:
            raise ValueError("shared_secret is only valid for HS256")
        if self.private_key is None and self.public_key is None:
            raise ValueError("asymmetric JWT configuration requires a private_key or public_key")

    def signing_key(self) -> str | bytes:
        """Return the configured signing key."""

        if self.algorithm is JWTAlgorithm.HS256:
            return self._shared_secret()
        if self.private_key is None:
            raise InvalidInputError("signing key is not configured")
        return self.private_key

    def verification_key(self) -> VerificationKey:
        """Return the configured verification key."""

        if self.algorithm is JWTAlgorithm.HS256:
            return self._shared_secret()
        if self.public_key is not None:
            return self.public_key
        if self.private_key is None:
            raise InvalidInputError("verification key is not configured")
        private_key = (
            self.private_key.encode("utf-8") if isinstance(self.private_key, str) else self.private_key
        )
        loaded = serialization.load_pem_private_key(private_key, password=None)
        public_key = loaded.public_key()
        if isinstance(
            public_key,
            rsa.RSAPublicKey | ec.EllipticCurvePublicKey | ed25519.Ed25519PublicKey | ed448.Ed448PublicKey,
        ):
            return public_key
        raise InvalidInputError("verification key is not configured")

    def _shared_secret(self) -> str | bytes:
        if self.shared_secret is None:
            raise InvalidInputError("shared_secret is not configured")
        return self.shared_secret

    def _shared_secret_bytes(self) -> bytes:
        secret = self._shared_secret()
        if isinstance(secret, str):
            return secret.encode("utf-8")
        return secret


class JWTService:
    """JWT token generation and validation."""

    def __init__(self, config: JWTConfig) -> None:
        self._config = config

    @property
    def config(self) -> JWTConfig:
        """Return the active JWT configuration."""

        return self._config

    def generate(self, claims: Claims, expires_in: int | None = None) -> str:
        """Sign a JWT with registered claims enforced by policy."""

        now = int(time())
        ttl = expires_in if expires_in is not None else self._config.default_ttl
        payload: Claims = dict(claims)
        self._validate_static_claims(payload)
        payload["iss"] = self._config.issuer
        payload["aud"] = self._config.audience
        payload.setdefault("iat", now)
        payload.setdefault("nbf", now)
        payload.setdefault("exp", now + ttl)

        headers = {"typ": "JWT"}
        if self._config.key_id:
            headers["kid"] = self._config.key_id

        return jwt.encode(
            payload,
            self._config.signing_key(),
            algorithm=self._config.algorithm.value,
            headers=headers,
        )

    def validate(self, token: str) -> Claims:
        """Validate *token* and return claims."""

        header = self._validated_header(token)
        try:
            claims = jwt.decode(
                token,
                self._config.verification_key(),
                algorithms=[self._config.algorithm.value],
                issuer=self._config.issuer,
                audience=self._config.audience,
                leeway=timedelta(seconds=self._config.leeway_seconds),
                options={"require": list(_REQUIRED_CLAIMS)},
            )
        except jwt.PyJWTError as exc:
            raise InvalidInputError("invalid token") from exc

        if header.get("kid") and self._config.key_id and header["kid"] != self._config.key_id:
            raise InvalidInputError("invalid token")
        return claims

    def decode_unverified(self, token: str) -> Claims:
        """Decode *token* without signature verification for diagnostics."""

        self._ensure_token_shape(token)
        try:
            return jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_exp": False,
                    "verify_iat": False,
                    "verify_nbf": False,
                    "verify_iss": False,
                    "verify_aud": False,
                },
            )
        except jwt.PyJWTError as exc:
            raise InvalidInputError("cannot decode token") from exc

    def _validated_header(self, token: str) -> dict[str, object]:
        self._ensure_token_shape(token)
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError as exc:
            raise InvalidInputError("invalid token") from exc

        algorithm = header.get("alg")
        if algorithm == "none" or algorithm != self._config.algorithm.value:
            raise InvalidInputError("invalid token")
        return header

    @staticmethod
    def _ensure_token_shape(token: str) -> None:
        if not token or token.isspace() or token.count(".") != 2:
            raise InvalidInputError("invalid token")

    def _validate_static_claims(self, claims: Claims) -> None:
        issuer = claims.get("iss")
        audience = claims.get("aud")
        if issuer is not None and issuer != self._config.issuer:
            raise InvalidInputError("issuer must match configured issuer")
        if audience is not None and audience != self._config.audience:
            raise InvalidInputError("audience must match configured audience")

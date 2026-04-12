"""API key generation, hashing, and validation."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Key:
    """API key metadata (never stores the plaintext)."""

    id: str
    owner_id: str
    name: str
    key_hash: str
    key_prefix: str
    scopes: list[str] = field(default_factory=list)
    is_active: bool = True
    expires_at: datetime | None = None
    grace_ends_at: datetime | None = None
    rotated_by_id: str = ""
    last_used_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_expired_past_grace(self) -> bool:
        """Return True if the key is expired and beyond its grace period."""
        now = datetime.now(UTC)
        if self.grace_ends_at is not None and now > self.grace_ends_at:
            return True
        if self.expires_at is not None and now > self.expires_at and self.grace_ends_at is None:
            return True
        return False


@dataclass(frozen=True)
class GenerateResult:
    """Result of key generation — contains the plaintext shown once."""

    plain_key: str
    key_hash: str
    prefix: str


def generate(prefix: str = "") -> GenerateResult:
    """Generate a new random API key with the given prefix.

    The key is ``prefix`` + 32 hex characters (16 random bytes).
    """
    random_hex = os.urandom(16).hex()
    plain_key = prefix + random_hex
    key_hash = hash_key(plain_key)
    display_prefix = plain_key[:8] if len(plain_key) > 8 else plain_key
    return GenerateResult(plain_key=plain_key, key_hash=key_hash, prefix=display_prefix)


def hash_key(plain_key: str) -> str:
    """Return the SHA-256 hex digest of a plaintext API key."""
    return hashlib.sha256(plain_key.encode()).hexdigest()


class KeyValidationError(Exception):
    """Raised when an API key fails validation."""


def validate(key: Key) -> None:
    """Check that a key is usable (active and not expired past grace).

    Raises ``KeyValidationError`` if the key is revoked or expired.
    """
    if not key.is_active:
        raise KeyValidationError("key is revoked")
    if key.is_expired_past_grace():
        raise KeyValidationError("key is expired")

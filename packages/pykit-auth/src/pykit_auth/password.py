"""Password hashing mirroring gokit auth/password.Hasher."""

from __future__ import annotations

import hashlib
import os
from enum import StrEnum

import bcrypt


class HashAlgorithm(StrEnum):
    """Supported password hashing algorithms."""

    BCRYPT = "bcrypt"
    ARGON2 = "argon2"


class PasswordHasher:
    """Password hashing and verification.

    Supports bcrypt (default) and argon2id via :mod:`hashlib`.
    """

    def __init__(
        self,
        algorithm: HashAlgorithm = HashAlgorithm.BCRYPT,
        rounds: int = 12,
    ) -> None:
        self._algorithm = algorithm
        self._rounds = rounds

    # -- Public API ------------------------------------------------------------

    def hash(self, password: str) -> str:
        """Return a hashed representation of *password*."""
        if self._algorithm == HashAlgorithm.BCRYPT:
            return self._hash_bcrypt(password)
        return self._hash_argon2(password)

    def verify(self, password: str, hashed: str) -> bool:
        """Return ``True`` if *password* matches *hashed*."""
        if self._algorithm == HashAlgorithm.BCRYPT:
            return self._verify_bcrypt(password, hashed)
        return self._verify_argon2(password, hashed)

    # -- Bcrypt ----------------------------------------------------------------

    def _hash_bcrypt(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=self._rounds)).decode()

    @staticmethod
    def _verify_bcrypt(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except ValueError:
            return False

    # -- Argon2id (stdlib hashlib) ---------------------------------------------

    def _hash_argon2(self, password: str) -> str:
        salt = os.urandom(16)
        raw = hashlib.scrypt(
            password.encode(),
            salt=salt,
            n=2**self._rounds,
            r=8,
            p=1,
            dklen=32,
        )
        # Store as salt$hash in hex so verify can reconstruct.
        return f"{salt.hex()}${raw.hex()}"

    def _verify_argon2(self, password: str, hashed: str) -> bool:
        try:
            salt_hex, hash_hex = hashed.split("$", 1)
            salt = bytes.fromhex(salt_hex)
            expected = bytes.fromhex(hash_hex)
        except (ValueError, IndexError):
            return False

        raw = hashlib.scrypt(
            password.encode(),
            salt=salt,
            n=2**self._rounds,
            r=8,
            p=1,
            dklen=len(expected),
        )
        # Constant-time comparison
        return len(raw) == len(expected) and all(a == b for a, b in zip(raw, expected, strict=True))

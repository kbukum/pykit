"""Password hashing mirroring gokit auth/password.Hasher."""

from __future__ import annotations

import hashlib
import hmac
import os
from enum import StrEnum

import bcrypt

try:
    from argon2 import PasswordHasher as _Argon2Hasher

    _ARGON2 = _Argon2Hasher()
    _ARGON2_AVAILABLE = True
except ImportError:
    _ARGON2_AVAILABLE = False


class HashAlgorithm(StrEnum):
    """Supported password hashing algorithms."""

    BCRYPT = "bcrypt"
    ARGON2 = "argon2"
    SCRYPT = "scrypt"


class PasswordHasher:
    """Password hashing and verification.

    Supports bcrypt (default), argon2id via argon2-cffi, and scrypt via stdlib.
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
        if self._algorithm == HashAlgorithm.ARGON2:
            if not _ARGON2_AVAILABLE:
                raise RuntimeError(
                    "argon2-cffi is required for ARGON2. Install with: pip install argon2-cffi"
                )
            return _ARGON2.hash(password)
        return self._hash_scrypt(password)

    def verify(self, password: str, hashed: str) -> bool:
        """Return ``True`` if *password* matches *hashed*."""
        if self._algorithm == HashAlgorithm.BCRYPT:
            return self._verify_bcrypt(password, hashed)
        if self._algorithm == HashAlgorithm.ARGON2:
            if not _ARGON2_AVAILABLE:
                raise RuntimeError("argon2-cffi is required for ARGON2.")
            try:
                return bool(_ARGON2.verify(hashed, password))
            except Exception:
                return False
        return self._verify_scrypt(password, hashed)

    # -- Bcrypt ----------------------------------------------------------------

    def _hash_bcrypt(self, password: str) -> str:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=self._rounds)).decode()

    @staticmethod
    def _verify_bcrypt(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode(), hashed.encode())
        except ValueError:
            return False

    # -- Scrypt (stdlib) -------------------------------------------------------

    def _hash_scrypt(self, password: str) -> str:
        salt = os.urandom(16)
        raw = hashlib.scrypt(
            password.encode(),
            salt=salt,
            n=2**self._rounds,
            r=8,
            p=1,
            dklen=32,
        )
        return f"{salt.hex()}${raw.hex()}"

    def _verify_scrypt(self, password: str, hashed: str) -> bool:
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
        return hmac.compare_digest(raw, expected)

"""Password hashing with Argon2id defaults and bcrypt migration fallback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import bcrypt
from argon2 import PasswordHasher as Argon2Hasher
from argon2 import Type as Argon2Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class HashAlgorithm(StrEnum):
    """Supported password hashing algorithms."""

    ARGON2ID = "argon2id"
    BCRYPT = "bcrypt"


@dataclass(frozen=True, slots=True)
class PasswordHashPolicy:
    """Password hashing policy."""

    default_algorithm: HashAlgorithm = HashAlgorithm.ARGON2ID
    memory_cost_kib: int = 65_536
    time_cost: int = 3
    parallelism: int = 4
    hash_len: int = 32
    salt_len: int = 16
    bcrypt_rounds: int = 12

    def __post_init__(self) -> None:
        if self.memory_cost_kib < 65_536:
            raise ValueError("argon2id memory_cost_kib must be at least 65536")
        if self.time_cost < 3:
            raise ValueError("argon2id time_cost must be at least 3")
        if self.parallelism < 1:
            raise ValueError("argon2id parallelism must be at least 1")
        if self.bcrypt_rounds < 12:
            raise ValueError("bcrypt_rounds must be at least 12")


class PasswordHasher:
    """Password hashing and verification.

    New hashes are produced with Argon2id by default. bcrypt verification is retained
    as an explicit migration fallback for pre-existing hashes.
    """

    def __init__(self, policy: PasswordHashPolicy | None = None) -> None:
        self._policy = policy or PasswordHashPolicy()
        self._argon2 = Argon2Hasher(
            time_cost=self._policy.time_cost,
            memory_cost=self._policy.memory_cost_kib,
            parallelism=self._policy.parallelism,
            hash_len=self._policy.hash_len,
            salt_len=self._policy.salt_len,
            type=Argon2Type.ID,
        )

    @property
    def policy(self) -> PasswordHashPolicy:
        """Return the active password hashing policy."""

        return self._policy

    def hash(self, password: str) -> str:
        """Return a hash for *password* using the configured default algorithm."""

        if self._policy.default_algorithm is HashAlgorithm.BCRYPT:
            return self._hash_bcrypt(password)
        return self._argon2.hash(password)

    def verify(self, password: str, hashed: str) -> bool:
        """Return ``True`` when *password* matches *hashed*."""

        algorithm = self.identify(hashed)
        if algorithm is None:
            return False
        if algorithm is HashAlgorithm.BCRYPT:
            return self._verify_bcrypt(password, hashed)
        return self._verify_argon2id(password, hashed)

    def needs_rehash(self, hashed: str) -> bool:
        """Return ``True`` when *hashed* should be replaced with the current default."""

        algorithm = self.identify(hashed)
        if algorithm is None:
            return True
        if algorithm is not self._policy.default_algorithm:
            return True
        if algorithm is HashAlgorithm.ARGON2ID:
            try:
                return self._argon2.check_needs_rehash(hashed)
            except InvalidHashError:
                return True
        return False

    @staticmethod
    def identify(hashed: str) -> HashAlgorithm | None:
        """Identify the algorithm used for *hashed*."""

        if hashed.startswith("$argon2id$"):
            return HashAlgorithm.ARGON2ID
        if hashed.startswith("$2"):
            return HashAlgorithm.BCRYPT
        return None

    def _hash_bcrypt(self, password: str) -> str:
        return bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt(rounds=self._policy.bcrypt_rounds)
        ).decode("utf-8")

    @staticmethod
    def _verify_bcrypt(password: str, hashed: str) -> bool:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
        except ValueError:
            return False

    def _verify_argon2id(self, password: str, hashed: str) -> bool:
        try:
            return bool(self._argon2.verify(hashed, password))
        except (InvalidHashError, VerificationError, VerifyMismatchError):
            return False

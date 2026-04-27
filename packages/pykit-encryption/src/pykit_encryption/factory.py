"""Factory function and algorithm enum for creating encryptors."""

from __future__ import annotations

from enum import Enum

from pykit_encryption.aesgcm import AESGCMEncryptor
from pykit_encryption.base import Encryptor
from pykit_encryption.fernet import FernetEncryptor


class Algorithm(Enum):
    """Supported encryption algorithms."""

    AES_GCM = "aes-gcm"
    FERNET = "fernet"


_REGISTRY: dict[Algorithm, type[Encryptor]] = {
    Algorithm.AES_GCM: AESGCMEncryptor,
    Algorithm.FERNET: FernetEncryptor,
}


def new_encryptor(key: str, algorithm: Algorithm = Algorithm.AES_GCM) -> Encryptor:
    """Create an :class:`Encryptor` for the given *algorithm*.

    This mirrors gokit's ``encryption.New(key, opts...)`` factory.
    """
    cls = _REGISTRY.get(algorithm)
    if cls is None:
        raise ValueError(f"unsupported algorithm: {algorithm!r}")
    return cls(key)  # type: ignore[call-arg]

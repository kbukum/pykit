"""Factory function and algorithm enum for creating encryptors."""

from __future__ import annotations

from enum import Enum

from pykit_encryption.aesgcm import AESGCMEncryptor
from pykit_encryption.base import Encryptor
from pykit_encryption.chacha20 import ChaCha20Encryptor
from pykit_encryption.fernet import FernetEncryptor


class Algorithm(Enum):
    """Supported encryption algorithms."""

    AES_GCM = "aes-gcm"
    CHACHA20 = "chacha20-poly1305"
    FERNET = "fernet"


_REGISTRY: dict[Algorithm, type[Encryptor]] = {
    Algorithm.AES_GCM: AESGCMEncryptor,
    Algorithm.CHACHA20: ChaCha20Encryptor,
    Algorithm.FERNET: FernetEncryptor,
}


def new_encryptor(key: str, algorithm: Algorithm = Algorithm.AES_GCM) -> Encryptor:
    """Create an :class:`Encryptor` for the given *algorithm*.

    Args:
        key: The passphrase used for key derivation.
        algorithm: The encryption algorithm to use (default: AES-GCM).

    Returns:
        An Encryptor instance for the chosen algorithm.

    Raises:
        ValueError: If the algorithm is not supported.
    """
    cls = _REGISTRY.get(algorithm)
    if cls is None:
        raise ValueError(f"unsupported algorithm: {algorithm!r}")
    return cls(key)  # type: ignore[call-arg]

"""Shared test configuration for pykit-encryption.

PBKDF2 iteration count is reduced from the production value (600,000) to a
small value (1,000) so the test suite completes in seconds rather than minutes.
Each encrypt/decrypt call invokes the KDF once; 600K iterations x hundreds of
calls would be impractically slow in CI.

The security property tested by the iteration count (brute-force resistance) is
not relevant to unit tests; the cryptographic correctness of the primitives
(key derivation determinism, ciphertext format, authenticated decryption) is
fully exercised at 1,000 iterations.
"""

from __future__ import annotations

import pykit_encryption.aesgcm as _aesgcm
import pykit_encryption.chacha20 as _chacha20

_aesgcm._PBKDF2_ITERATIONS = 1_000
_chacha20._PBKDF2_ITERATIONS = 1_000

"""pykit-auth-apikey — API key generation, hashing, validation, and rotation."""

from __future__ import annotations

from pykit_auth_apikey.apikey import (
    GenerateResult,
    Key,
    KeyValidationError,
    generate,
    hash_key,
    validate,
)
from pykit_auth_apikey.middleware import APIKeyMiddleware, KeyValidator
from pykit_auth_apikey.rotation import (
    DEFAULT_GRACE_PERIOD,
    RotationConfig,
    RotationResult,
    rotate,
)
from pykit_auth_apikey.store import Store

__all__ = [
    "DEFAULT_GRACE_PERIOD",
    "APIKeyMiddleware",
    "GenerateResult",
    "Key",
    "KeyValidationError",
    "KeyValidator",
    "RotationConfig",
    "RotationResult",
    "Store",
    "generate",
    "hash_key",
    "rotate",
    "validate",
]

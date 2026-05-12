"""Redis adapter tests."""

from __future__ import annotations

import pytest

from pykit_cache import CacheConfig
from pykit_errors import InvalidInputError
from pykit_cache_redis import RedisCacheBackend


def test_redis_backend_rejects_byte_responses() -> None:
    cfg = CacheConfig(decode_responses=False)
    with pytest.raises(InvalidInputError, match="decode_responses=True"):
        RedisCacheBackend(cfg)

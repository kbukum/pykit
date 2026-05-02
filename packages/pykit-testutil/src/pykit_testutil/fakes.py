"""Reusable fake backends for unit tests."""

from __future__ import annotations


class FakeAsyncKeyValue:
    """Small async key-value backend for cache-style unit tests."""

    def __init__(self, *, decode_responses: bool = True) -> None:
        self._values: dict[str, str | bytes] = {}
        self._decode_responses = decode_responses
        self.closed = False

    async def get(self, key: str) -> str | bytes | None:
        """Return a stored value or ``None``."""
        return self._values.get(key)

    async def set(self, key: str, value: str | bytes, ex: int | None = None) -> None:
        """Store a value, rejecting invalid Redis-compatible expiration values."""
        if ex is not None and ex <= 0:
            raise ValueError("invalid expire time")
        if isinstance(value, bytes) and self._decode_responses:
            self._values[key] = value.decode()
            return
        self._values[key] = value

    async def delete(self, *keys: str) -> int:
        """Delete keys and return the number removed."""
        removed = 0
        for key in keys:
            if key in self._values:
                removed += 1
                del self._values[key]
        return removed

    async def exists(self, *keys: str) -> int:
        """Return the number of keys present."""
        return sum(1 for key in keys if key in self._values)

    def ping(self) -> bool:
        """Return healthy status."""
        return True

    async def aclose(self) -> None:
        """Mark the fake backend closed."""
        self.closed = True

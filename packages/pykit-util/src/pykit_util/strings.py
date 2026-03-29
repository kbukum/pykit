"""String utilities — pure Python, zero dependencies."""

from __future__ import annotations

import re
import unicodedata

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def coalesce[T](*values: T | None) -> T | None:
    """Return the first truthy value, or ``None``."""
    for v in values:
        if v:
            return v
    return None


def slug(text: str) -> str:
    """Convert *text* into a URL-safe slug (lowercase, hyphens)."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _SLUG_RE.sub("-", text)
    return text.strip("-")


def truncate(text: str, max_len: int, suffix: str = "...") -> str:
    """Truncate *text* to *max_len* characters, appending *suffix* if truncated."""
    if len(text) <= max_len:
        return text
    if max_len <= len(suffix):
        return text[:max_len]
    return text[: max_len - len(suffix)] + suffix

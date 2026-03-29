"""Sanitization utilities — pure Python, zero dependencies.

NOTE: ``is_safe_string`` is a **defense-in-depth** helper and must NOT be
relied upon as a security boundary.  Always use parameterised queries,
proper escaping, and framework-level protections.
"""

from __future__ import annotations

import re
import unicodedata

# Control characters (C0/C1) excluding common whitespace (tab, newline, carriage-return).
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")

# Basic injection patterns (SQL, shell, path traversal, script tags).
_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(--|;)\s*(drop|alter|delete|update|insert|select|union)\b", re.IGNORECASE),
    re.compile(r"[`$](\(|{)", re.IGNORECASE),
    re.compile(r"\.\./"),
    re.compile(r"<\s*script", re.IGNORECASE),
]


def sanitize_string(s: str) -> str:
    """Trim whitespace and remove control characters."""
    s = unicodedata.normalize("NFC", s)
    s = _CONTROL_RE.sub("", s)
    return s.strip()


def sanitize_env_value(s: str) -> str:
    """Strip surrounding quotes and trim whitespace from an env-var value."""
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1]
    return s.strip()


def is_safe_string(s: str) -> bool:
    """Return ``False`` if *s* matches basic injection patterns.

    This is **defense-in-depth only** — never rely on it as a security boundary.
    """
    return all(not pattern.search(s) for pattern in _INJECTION_PATTERNS)

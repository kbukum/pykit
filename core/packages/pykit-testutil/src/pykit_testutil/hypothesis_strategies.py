"""Common hypothesis strategies for pykit test suites."""

from __future__ import annotations

from typing import Any

try:
    from hypothesis import strategies as st
    from hypothesis.strategies import SearchStrategy

    def error_codes() -> SearchStrategy[str]:
        """Generate valid error code strings."""
        return st.sampled_from(
            [
                "NOT_FOUND",
                "INVALID_INPUT",
                "UNAUTHORIZED",
                "FORBIDDEN",
                "INTERNAL",
                "SERVICE_UNAVAILABLE",
                "TIMEOUT",
                "CONFLICT",
            ]
        )

    def non_empty_text(max_size: int = 200) -> SearchStrategy[str]:
        """Generate non-empty printable text."""
        return st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs", "Po")),
            min_size=1,
            max_size=max_size,
        )

    def url_safe_text(max_size: int = 100) -> SearchStrategy[str]:
        """Generate URL-safe text (no spaces, no special chars)."""
        return st.text(
            alphabet="abcdefghijklmnopqrstuvwxyz0123456789-_",
            min_size=1,
            max_size=max_size,
        )

    __all__ = ["error_codes", "non_empty_text", "url_safe_text"]

except ImportError:
    # hypothesis not installed — stubs so imports don't break
    def error_codes() -> Any:
        raise ImportError("hypothesis is required: pip install hypothesis")

    def non_empty_text(max_size: int = 200) -> Any:
        raise ImportError("hypothesis is required: pip install hypothesis")

    def url_safe_text(max_size: int = 100) -> Any:
        raise ImportError("hypothesis is required: pip install hypothesis")

    __all__ = ["error_codes", "non_empty_text", "url_safe_text"]

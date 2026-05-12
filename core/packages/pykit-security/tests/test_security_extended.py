"""Extended security package tests."""

from __future__ import annotations

import pytest

from pykit_errors import InvalidInputError
from pykit_security import CORSConfig, SecurityHeadersPolicy, extract_bearer_token


def test_hsts_only_added_for_tls() -> None:
    assert "Strict-Transport-Security" not in SecurityHeadersPolicy().build_headers(tls_enabled=False)


def test_missing_bearer_header_is_rejected() -> None:
    with pytest.raises(InvalidInputError):
        extract_bearer_token({})


def test_cors_max_age_validation() -> None:
    with pytest.raises(ValueError):
        CORSConfig(max_age_seconds=-1)

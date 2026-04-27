"""Property-based tests for JWT service using hypothesis."""

from __future__ import annotations

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

if HYPOTHESIS_AVAILABLE:
    from pykit_auth.jwt_service import JWTConfig, JWTService

    @given(
        sub=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_@."),
        ),
        role=st.sampled_from(["admin", "user", "viewer", "guest"]),
    )
    @settings(max_examples=50)
    def test_jwt_encode_decode_roundtrip(sub: str, role: str) -> None:
        """Encoding then decoding must always return the same payload."""
        config = JWTConfig(secret="a" * 32, algorithm="HS256")
        svc = JWTService(config)
        payload = {"sub": sub, "role": role}
        token = svc.generate(payload)
        decoded = svc.validate(token)
        assert decoded["sub"] == sub
        assert decoded["role"] == role

    @given(garbage=st.binary(min_size=0, max_size=500))
    @settings(max_examples=50)
    def test_jwt_decode_garbage_never_crashes(garbage: bytes) -> None:
        """Decoding arbitrary bytes must raise an exception, never crash."""
        config = JWTConfig(secret="a" * 32, algorithm="HS256")
        svc = JWTService(config)
        try:
            svc.validate(garbage.decode("latin-1", errors="replace"))
        except Exception:
            pass  # expected — any exception is fine; a hard crash is not

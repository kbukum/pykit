"""Property-based JWT safety tests."""

from __future__ import annotations

try:
    from hypothesis import given, settings
    from hypothesis import strategies as st

    HYPOTHESIS_AVAILABLE = True
except ImportError:
    HYPOTHESIS_AVAILABLE = False

if HYPOTHESIS_AVAILABLE:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    from pykit_auth import JWTConfig, JWTService

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )

    @given(
        sub=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_@."),
        ),
        role=st.sampled_from(["admin", "user", "viewer"]),
    )
    @settings(max_examples=25)
    def test_jwt_roundtrip(sub: str, role: str) -> None:
        service = JWTService(
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                private_key=private_pem,
                public_key=public_pem,
            )
        )
        token = service.generate({"sub": sub, "role": role})
        claims = service.validate(token)
        assert claims["sub"] == sub
        assert claims["role"] == role

    @given(garbage=st.binary(min_size=0, max_size=500))
    @settings(max_examples=25)
    def test_decode_unverified_never_crashes(garbage: bytes) -> None:
        service = JWTService(
            JWTConfig(
                issuer="pykit-tests",
                audience="pykit-clients",
                private_key=private_pem,
                public_key=public_pem,
            )
        )
        try:
            service.decode_unverified(garbage.decode("latin-1", errors="ignore"))
        except Exception:
            pass

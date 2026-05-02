"""Fuzz test for JWT decode — should never hard-crash on arbitrary input."""

import sys

import atheris

with atheris.instrument_imports():
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        from pykit_auth.jwt import JWTConfig, JWTService

        JWT_AVAILABLE = True
        _private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _private_pem = _private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        _public_pem = (
            _private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode("utf-8")
        )
    except ImportError:
        JWT_AVAILABLE = False


def TestOneInput(data: bytes) -> None:
    if not JWT_AVAILABLE:
        return
    fdp = atheris.FuzzedDataProvider(data)
    try:
        token = fdp.ConsumeUnicodeNoSurrogates(500)
        config = JWTConfig(
            issuer="fuzz-tests",
            audience="pykit-clients",
            private_key=_private_pem,
            public_key=_public_pem,
        )
        svc = JWTService(config)
        svc.decode_unverified(token)
    except Exception:
        pass  # any exception is fine; a hard crash is not


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()

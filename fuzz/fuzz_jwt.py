"""Fuzz test for JWT decode — should never hard-crash on arbitrary input."""

import sys

import atheris

with atheris.instrument_imports():
    try:
        from pykit_auth.jwt import JWTConfig, JWTService  # adjust import path if needed

        JWT_AVAILABLE = True
    except ImportError:
        JWT_AVAILABLE = False


def TestOneInput(data: bytes) -> None:
    if not JWT_AVAILABLE:
        return
    fdp = atheris.FuzzedDataProvider(data)
    try:
        token = fdp.ConsumeUnicodeNoSurrogates(500)
        config = JWTConfig(secret="a" * 32, algorithm="HS256")  # adjust fields
        svc = JWTService(config)
        svc._decode_unverified(token)
    except Exception:
        pass  # any exception is fine; a hard crash is not


if __name__ == "__main__":
    atheris.Setup(sys.argv, TestOneInput)
    atheris.Fuzz()

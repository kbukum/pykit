"""Tests for pykit-security."""

from __future__ import annotations

import ssl
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
except ImportError:  # pragma: no cover - optional test dependency
    pytest.skip("cryptography is required for TLS certificate tests", allow_module_level=True)

from pykit_errors import InvalidInputError
from pykit_security import CORSConfig, SecurityHeadersPolicy, TLSConfig, extract_bearer_token


@pytest.fixture
def cert_paths(tmp_path: Path) -> tuple[str, str, str]:
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    server_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(ca_subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .sign(ca_key, hashes.SHA256())
    )

    ca_path = tmp_path / "ca.pem"
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"
    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        server_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return str(ca_path), str(cert_path), str(key_path)


class TestTLSConfig:
    def test_default_minimum_is_tls13(self) -> None:
        assert TLSConfig().min_version == ssl.TLSVersion.TLSv1_3

    def test_tls12_floor_is_enforced(self) -> None:
        with pytest.raises(ValueError, match=r"TLS 1\.2"):
            TLSConfig(min_version=ssl.TLSVersion.TLSv1).validate()

    def test_build_client_and_server(self, cert_paths: tuple[str, str, str]) -> None:
        ca_file, cert_file, key_file = cert_paths
        config = TLSConfig(ca_file=ca_file, cert_file=cert_file, key_file=key_file)
        config.validate()

        client_context = config.build()
        server_context = config.build_server()

        assert client_context is not None
        assert server_context is not None
        assert client_context.minimum_version == ssl.TLSVersion.TLSv1_3
        assert server_context.verify_mode == ssl.CERT_REQUIRED

    def test_skip_verify_and_invalid_paths(self) -> None:
        config = TLSConfig(skip_verify=True)
        context = config.build()
        assert context is not None
        assert context.verify_mode == ssl.CERT_NONE

        with pytest.raises(FileNotFoundError):
            TLSConfig(ca_file="/does/not/exist").validate()

        with pytest.raises(ValueError, match="together"):
            TLSConfig(cert_file="cert.pem").validate()


class TestHeadersAndTokens:
    def test_security_headers_are_secure_by_default(self) -> None:
        headers = SecurityHeadersPolicy().build_headers(tls_enabled=True)
        assert headers["Strict-Transport-Security"].startswith("max-age=")
        assert headers["Content-Security-Policy"].startswith("default-src")
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"

    def test_cors_requires_exact_origin(self) -> None:
        config = CORSConfig(allowed_origins=("https://app.example.com",), allow_credentials=True)
        headers = config.build_preflight_headers("https://app.example.com", request_headers=("X-Trace-Id",))
        assert headers["Access-Control-Allow-Origin"] == "https://app.example.com"
        assert "X-Trace-Id" in headers["Access-Control-Allow-Headers"]

        with pytest.raises(InvalidInputError):
            config.build_preflight_headers("https://evil.example.com")

        with pytest.raises(InvalidInputError):
            CORSConfig().build_preflight_headers("https://app.example.com")

    def test_extract_bearer_token_rejects_query_tokens(self) -> None:
        token = extract_bearer_token({"Authorization": "Bearer token-1"})
        assert token == "token-1"

        with pytest.raises(InvalidInputError):
            extract_bearer_token(
                {"Authorization": "Bearer token-1"},
                query_params={"access_token": "forbidden"},
            )

        with pytest.raises(InvalidInputError):
            extract_bearer_token(
                {"Authorization": "Bearer token-1"},
                query_params={"Access_Token": "forbidden"},
            )

        with pytest.raises(InvalidInputError):
            extract_bearer_token({"Authorization": "Bearer  token-1 extra"})

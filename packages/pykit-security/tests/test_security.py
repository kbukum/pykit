"""Comprehensive tests for pykit-security TLS configuration."""

from __future__ import annotations

import ssl
from pathlib import Path

import pytest

from pykit_security import TLSConfig

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------


class TestTLSConfigDefaults:
    def test_default_values(self):
        cfg = TLSConfig()
        assert cfg.skip_verify is False
        assert cfg.ca_file == ""
        assert cfg.cert_file == ""
        assert cfg.key_file == ""
        assert cfg.server_hostname == ""
        assert cfg.min_version == ssl.TLSVersion.TLSv1_2


# ---------------------------------------------------------------------------
# is_enabled
# ---------------------------------------------------------------------------


class TestIsEnabled:
    def test_disabled_by_default(self):
        assert TLSConfig().is_enabled() is False

    def test_enabled_with_skip_verify(self):
        assert TLSConfig(skip_verify=True).is_enabled() is True

    def test_enabled_with_ca_file(self):
        assert TLSConfig(ca_file="/some/ca.pem").is_enabled() is True

    def test_enabled_with_cert_file(self):
        assert TLSConfig(cert_file="/some/cert.pem").is_enabled() is True

    def test_enabled_with_server_hostname(self):
        assert TLSConfig(server_hostname="example.com").is_enabled() is True

    def test_disabled_with_only_key_file(self):
        # key_file alone does not enable TLS (cert_file is the trigger)
        assert TLSConfig(key_file="/some/key.pem").is_enabled() is False


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


class TestValidate:
    def test_valid_empty_config(self):
        TLSConfig().validate()  # should not raise

    def test_cert_without_key_raises(self):
        with pytest.raises(ValueError, match="Both cert_file and key_file"):
            TLSConfig(cert_file="/some/cert.pem").validate()

    def test_key_without_cert_raises(self):
        with pytest.raises(ValueError, match="Both cert_file and key_file"):
            TLSConfig(key_file="/some/key.pem").validate()

    def test_both_cert_and_key_is_valid(self, tmp_path: Path):
        cert = tmp_path / "cert.pem"
        key = tmp_path / "key.pem"
        cert.write_text("cert")
        key.write_text("key")
        TLSConfig(cert_file=str(cert), key_file=str(key)).validate()

    def test_nonexistent_ca_file_raises(self):
        with pytest.raises(FileNotFoundError, match="CA file not found"):
            TLSConfig(ca_file="/nonexistent/ca.pem").validate()

    def test_nonexistent_cert_file_raises(self, tmp_path: Path):
        key = tmp_path / "key.pem"
        key.write_text("key")
        with pytest.raises(FileNotFoundError, match="Cert file not found"):
            TLSConfig(cert_file="/nonexistent/cert.pem", key_file=str(key)).validate()

    def test_nonexistent_key_file_raises(self, tmp_path: Path):
        cert = tmp_path / "cert.pem"
        cert.write_text("cert")
        with pytest.raises(FileNotFoundError, match="Key file not found"):
            TLSConfig(cert_file=str(cert), key_file="/nonexistent/key.pem").validate()


# ---------------------------------------------------------------------------
# build (client-side)
# ---------------------------------------------------------------------------


class TestBuild:
    def test_returns_none_when_not_enabled(self):
        assert TLSConfig().build() is None

    def test_returns_ssl_context_with_skip_verify(self):
        ctx = TLSConfig(skip_verify=True).build()
        assert isinstance(ctx, ssl.SSLContext)
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_min_version_applied(self):
        cfg = TLSConfig(skip_verify=True, min_version=ssl.TLSVersion.TLSv1_3)
        ctx = cfg.build()
        assert ctx is not None
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3

    def test_default_min_version(self):
        ctx = TLSConfig(skip_verify=True).build()
        assert ctx is not None
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

    def test_server_hostname_enables_context(self):
        ctx = TLSConfig(server_hostname="example.com").build()
        assert isinstance(ctx, ssl.SSLContext)


# ---------------------------------------------------------------------------
# build_server (server-side)
# ---------------------------------------------------------------------------


class TestBuildServer:
    def test_returns_none_when_not_enabled(self):
        assert TLSConfig().build_server() is None

    def test_returns_server_context(self):
        ctx = TLSConfig(skip_verify=True).build_server()
        assert isinstance(ctx, ssl.SSLContext)

    def test_min_version_applied(self):
        cfg = TLSConfig(skip_verify=True, min_version=ssl.TLSVersion.TLSv1_3)
        ctx = cfg.build_server()
        assert ctx is not None
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3


# ---------------------------------------------------------------------------
# build with real self-signed certs (generated via ssl helpers)
# ---------------------------------------------------------------------------


class TestBuildWithCerts:
    """Test build/build_server with actual certificate files on disk."""

    @pytest.fixture
    def self_signed_certs(self, tmp_path: Path):
        """Generate a self-signed cert + key using the cryptography library (if available)
        or fall back to ssl module helpers."""
        try:
            import datetime

            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.x509.oid import NameOID

            key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
            subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")])
            cert = (
                x509.CertificateBuilder()
                .subject_name(subject)
                .issuer_name(issuer)
                .public_key(key.public_key())
                .serial_number(x509.random_serial_number())
                .not_valid_before(datetime.datetime.now(datetime.UTC))
                .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
                .sign(key, hashes.SHA256())
            )

            cert_path = tmp_path / "cert.pem"
            key_path = tmp_path / "key.pem"
            cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
            key_path.write_bytes(
                key.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.TraditionalOpenSSL,
                    serialization.NoEncryption(),
                )
            )
            return str(cert_path), str(key_path)
        except ImportError:
            pytest.skip("cryptography library not available")

    def test_build_with_cert_and_key(self, self_signed_certs: tuple[str, str]):
        cert_file, key_file = self_signed_certs
        cfg = TLSConfig(cert_file=cert_file, key_file=key_file, skip_verify=True)
        ctx = cfg.build()
        assert isinstance(ctx, ssl.SSLContext)

    def test_build_server_with_cert_and_key(self, self_signed_certs: tuple[str, str]):
        cert_file, key_file = self_signed_certs
        cfg = TLSConfig(cert_file=cert_file, key_file=key_file)
        ctx = cfg.build_server()
        assert isinstance(ctx, ssl.SSLContext)

    def test_build_with_ca_file(self, self_signed_certs: tuple[str, str]):
        cert_file, _key_file = self_signed_certs
        # Use the self-signed cert as its own CA
        cfg = TLSConfig(ca_file=cert_file, skip_verify=True)
        ctx = cfg.build()
        assert isinstance(ctx, ssl.SSLContext)

    def test_build_server_with_ca_requires_client_cert(self, self_signed_certs: tuple[str, str]):
        cert_file, key_file = self_signed_certs
        cfg = TLSConfig(ca_file=cert_file, cert_file=cert_file, key_file=key_file)
        ctx = cfg.build_server()
        assert ctx is not None
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    def test_validate_with_real_files(self, self_signed_certs: tuple[str, str]):
        cert_file, key_file = self_signed_certs
        cfg = TLSConfig(cert_file=cert_file, key_file=key_file, ca_file=cert_file)
        cfg.validate()  # should not raise

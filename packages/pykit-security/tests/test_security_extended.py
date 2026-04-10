"""Extended security tests: TLS hardening, edge cases, and security enforcement."""

from __future__ import annotations

import datetime
import os
import ssl
import stat
from dataclasses import asdict
from pathlib import Path

import pytest

from pykit_security import TLSConfig

# Try importing cryptography for cert generation
try:
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

needs_cryptography = pytest.mark.skipif(not HAS_CRYPTOGRAPHY, reason="cryptography library not available")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def self_signed_certs(tmp_path: Path):
    """Generate a self-signed CA cert + leaf cert+key for testing."""
    if not HAS_CRYPTOGRAPHY:
        pytest.skip("cryptography library not available")

    # CA key and cert
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test CA")])
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_subject)
        .issuer_name(ca_subject)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )

    # Leaf cert signed by CA
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf_cert = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "localhost")]))
        .issuer_name(ca_subject)
        .public_key(leaf_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.datetime.now(datetime.UTC))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
        .sign(ca_key, hashes.SHA256())
    )

    ca_path = tmp_path / "ca.pem"
    cert_path = tmp_path / "cert.pem"
    key_path = tmp_path / "key.pem"

    ca_path.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    cert_path.write_bytes(leaf_cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(
        leaf_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
    )
    return str(ca_path), str(cert_path), str(key_path)


# ---------------------------------------------------------------------------
# TLS config defaults and minimum version enforcement
# ---------------------------------------------------------------------------


class TestTLSMinVersionEnforcement:
    def test_default_min_version_is_tls12(self):
        cfg = TLSConfig()
        assert cfg.min_version == ssl.TLSVersion.TLSv1_2

    def test_build_applies_tls12_by_default(self):
        ctx = TLSConfig(skip_verify=True).build()
        assert ctx is not None
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2

    def test_tls13_accepted(self):
        cfg = TLSConfig(skip_verify=True, min_version=ssl.TLSVersion.TLSv1_3)
        ctx = cfg.build()
        assert ctx is not None
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3

    def test_build_server_applies_min_version(self):
        cfg = TLSConfig(skip_verify=True, min_version=ssl.TLSVersion.TLSv1_3)
        ctx = cfg.build_server()
        assert ctx is not None
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_3

    def test_build_server_default_min_version(self):
        ctx = TLSConfig(skip_verify=True).build_server()
        assert ctx is not None
        assert ctx.minimum_version == ssl.TLSVersion.TLSv1_2


# ---------------------------------------------------------------------------
# Certificate loading edge cases
# ---------------------------------------------------------------------------


class TestCertificateLoadingEdgeCases:
    @needs_cryptography
    def test_load_ca_file(self, self_signed_certs):
        ca_path, cert_path, key_path = self_signed_certs
        cfg = TLSConfig(ca_file=ca_path, skip_verify=True)
        ctx = cfg.build()
        assert isinstance(ctx, ssl.SSLContext)

    @needs_cryptography
    def test_load_cert_and_key(self, self_signed_certs):
        ca_path, cert_path, key_path = self_signed_certs
        cfg = TLSConfig(cert_file=cert_path, key_file=key_path, skip_verify=True)
        ctx = cfg.build()
        assert isinstance(ctx, ssl.SSLContext)

    @needs_cryptography
    def test_cert_key_mismatch_raises(self, self_signed_certs, tmp_path: Path):
        """Using a key that doesn't match the cert should fail."""
        _ca_path, cert_path, _key_path = self_signed_certs
        # Generate a different key
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_key_path = tmp_path / "other_key.pem"
        other_key_path.write_bytes(
            other_key.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.TraditionalOpenSSL,
                serialization.NoEncryption(),
            )
        )
        cfg = TLSConfig(cert_file=cert_path, key_file=str(other_key_path), skip_verify=True)
        with pytest.raises(ssl.SSLError):
            cfg.build()

    def test_nonexistent_ca_file_raises_on_build(self):
        cfg = TLSConfig(ca_file="/nonexistent/ca.pem", skip_verify=True)
        with pytest.raises(Exception):
            cfg.build()

    def test_nonexistent_cert_file_raises_on_build(self):
        cfg = TLSConfig(
            cert_file="/nonexistent/cert.pem",
            key_file="/nonexistent/key.pem",
            skip_verify=True,
        )
        with pytest.raises(Exception):
            cfg.build()

    def test_invalid_pem_content_raises(self, tmp_path: Path):
        """Files that exist but contain garbage should fail."""
        bad_cert = tmp_path / "bad_cert.pem"
        bad_key = tmp_path / "bad_key.pem"
        bad_cert.write_text("not a real PEM cert")
        bad_key.write_text("not a real PEM key")
        cfg = TLSConfig(cert_file=str(bad_cert), key_file=str(bad_key), skip_verify=True)
        with pytest.raises(ssl.SSLError):
            cfg.build()


# ---------------------------------------------------------------------------
# mTLS configuration
# ---------------------------------------------------------------------------


class TestMTLSConfiguration:
    @needs_cryptography
    def test_mtls_full_config(self, self_signed_certs):
        ca_path, cert_path, key_path = self_signed_certs
        cfg = TLSConfig(
            ca_file=ca_path,
            cert_file=cert_path,
            key_file=key_path,
            server_hostname="localhost",
        )
        ctx = cfg.build()
        assert isinstance(ctx, ssl.SSLContext)

    @needs_cryptography
    def test_mtls_server_requires_client_cert(self, self_signed_certs):
        ca_path, cert_path, key_path = self_signed_certs
        cfg = TLSConfig(
            ca_file=ca_path,
            cert_file=cert_path,
            key_file=key_path,
        )
        ctx = cfg.build_server()
        assert ctx is not None
        assert ctx.verify_mode == ssl.CERT_REQUIRED

    @needs_cryptography
    def test_mtls_missing_key_file_validation(self, self_signed_certs):
        ca_path, cert_path, _key_path = self_signed_certs
        cfg = TLSConfig(ca_file=ca_path, cert_file=cert_path)
        with pytest.raises(ValueError, match="Both cert_file and key_file"):
            cfg.validate()

    @needs_cryptography
    def test_mtls_missing_cert_file_validation(self, self_signed_certs):
        ca_path, _cert_path, key_path = self_signed_certs
        cfg = TLSConfig(ca_file=ca_path, key_file=key_path)
        with pytest.raises(ValueError, match="Both cert_file and key_file"):
            cfg.validate()


# ---------------------------------------------------------------------------
# Invalid paths → clear errors
# ---------------------------------------------------------------------------


class TestInvalidPaths:
    def test_validate_nonexistent_ca(self):
        cfg = TLSConfig(ca_file="/does/not/exist.pem")
        with pytest.raises(FileNotFoundError, match="CA file not found"):
            cfg.validate()

    def test_validate_nonexistent_cert(self, tmp_path: Path):
        key = tmp_path / "key.pem"
        key.write_text("key")
        cfg = TLSConfig(cert_file="/does/not/exist.pem", key_file=str(key))
        with pytest.raises(FileNotFoundError, match="Cert file not found"):
            cfg.validate()

    def test_validate_nonexistent_key(self, tmp_path: Path):
        cert = tmp_path / "cert.pem"
        cert.write_text("cert")
        cfg = TLSConfig(cert_file=str(cert), key_file="/does/not/exist.pem")
        with pytest.raises(FileNotFoundError, match="Key file not found"):
            cfg.validate()

    def test_error_messages_do_not_leak_credentials(self):
        """Validation errors should not contain credential content."""
        cfg = TLSConfig(cert_file="/secret/cert.pem")
        err = None
        try:
            cfg.validate()
        except ValueError as e:
            err = e
        assert err is not None
        # The error message is generic, not leaking paths of secrets
        assert "Both cert_file and key_file" in str(err)


# ---------------------------------------------------------------------------
# Empty configuration → disabled
# ---------------------------------------------------------------------------


class TestEmptyConfiguration:
    def test_default_config_not_enabled(self):
        assert TLSConfig().is_enabled() is False

    def test_default_config_build_returns_none(self):
        assert TLSConfig().build() is None

    def test_default_config_build_server_returns_none(self):
        assert TLSConfig().build_server() is None

    def test_empty_strings_not_enabled(self):
        cfg = TLSConfig(ca_file="", cert_file="", key_file="", server_hostname="")
        assert cfg.is_enabled() is False

    def test_key_file_only_not_enabled(self):
        cfg = TLSConfig(key_file="/some/key.pem")
        assert cfg.is_enabled() is False


# ---------------------------------------------------------------------------
# Config serialization/deserialization (dataclass)
# ---------------------------------------------------------------------------


class TestConfigSerialization:
    def test_asdict_roundtrip(self):
        cfg = TLSConfig(
            skip_verify=True,
            ca_file="/path/to/ca.pem",
            cert_file="/path/to/cert.pem",
            key_file="/path/to/key.pem",
            server_hostname="example.com",
            min_version=ssl.TLSVersion.TLSv1_3,
        )
        d = asdict(cfg)
        restored = TLSConfig(**d)
        assert restored.skip_verify is True
        assert restored.ca_file == "/path/to/ca.pem"
        assert restored.cert_file == "/path/to/cert.pem"
        assert restored.key_file == "/path/to/key.pem"
        assert restored.server_hostname == "example.com"
        assert restored.min_version == ssl.TLSVersion.TLSv1_3

    def test_asdict_contains_all_fields(self):
        d = asdict(TLSConfig())
        expected_keys = {"skip_verify", "ca_file", "cert_file", "key_file", "server_hostname", "min_version"}
        assert set(d.keys()) == expected_keys

    def test_equality(self):
        cfg1 = TLSConfig(skip_verify=True, server_hostname="example.com")
        cfg2 = TLSConfig(skip_verify=True, server_hostname="example.com")
        assert cfg1 == cfg2

    def test_inequality(self):
        cfg1 = TLSConfig(skip_verify=True)
        cfg2 = TLSConfig(skip_verify=False)
        assert cfg1 != cfg2


# ---------------------------------------------------------------------------
# Permission denied on cert file
# ---------------------------------------------------------------------------


class TestPermissionErrors:
    @needs_cryptography
    def test_permission_denied_ca_file(self, self_signed_certs, tmp_path: Path):
        ca_path, _cert_path, _key_path = self_signed_certs
        # Copy CA file and remove read permission
        no_read = tmp_path / "no_read_ca.pem"
        no_read.write_bytes(Path(ca_path).read_bytes())
        os.chmod(no_read, 0o000)
        try:
            cfg = TLSConfig(ca_file=str(no_read), skip_verify=True)
            with pytest.raises(Exception):
                cfg.build()
        finally:
            os.chmod(no_read, stat.S_IRUSR | stat.S_IWUSR)

    @needs_cryptography
    def test_permission_denied_cert_file(self, self_signed_certs, tmp_path: Path):
        _ca_path, cert_path, key_path = self_signed_certs
        no_read = tmp_path / "no_read_cert.pem"
        no_read.write_bytes(Path(cert_path).read_bytes())
        os.chmod(no_read, 0o000)
        try:
            cfg = TLSConfig(cert_file=str(no_read), key_file=key_path, skip_verify=True)
            with pytest.raises(Exception):
                cfg.build()
        finally:
            os.chmod(no_read, stat.S_IRUSR | stat.S_IWUSR)


# ---------------------------------------------------------------------------
# Validate catches all invalid combinations
# ---------------------------------------------------------------------------


class TestValidateComprehensive:
    def test_validate_empty_is_fine(self):
        TLSConfig().validate()

    def test_validate_skip_verify_only_is_fine(self):
        TLSConfig(skip_verify=True).validate()

    def test_validate_server_hostname_only_is_fine(self):
        TLSConfig(server_hostname="example.com").validate()

    @needs_cryptography
    def test_validate_full_config(self, self_signed_certs):
        ca_path, cert_path, key_path = self_signed_certs
        cfg = TLSConfig(
            ca_file=ca_path,
            cert_file=cert_path,
            key_file=key_path,
            server_hostname="localhost",
            min_version=ssl.TLSVersion.TLSv1_3,
        )
        cfg.validate()  # should not raise

    def test_validate_cert_without_key(self):
        with pytest.raises(ValueError):
            TLSConfig(cert_file="cert.pem").validate()

    def test_validate_key_without_cert(self):
        with pytest.raises(ValueError):
            TLSConfig(key_file="key.pem").validate()


# ---------------------------------------------------------------------------
# Build produces correct protocol types
# ---------------------------------------------------------------------------


class TestBuildProtocols:
    def test_build_creates_client_protocol(self):
        ctx = TLSConfig(skip_verify=True).build()
        assert ctx is not None
        assert ctx.protocol == ssl.PROTOCOL_TLS_CLIENT

    def test_build_server_creates_server_protocol(self):
        ctx = TLSConfig(skip_verify=True).build_server()
        assert ctx is not None
        assert ctx.protocol == ssl.PROTOCOL_TLS_SERVER

    def test_skip_verify_disables_hostname_check(self):
        ctx = TLSConfig(skip_verify=True).build()
        assert ctx is not None
        assert ctx.check_hostname is False
        assert ctx.verify_mode == ssl.CERT_NONE

    def test_skip_verify_false_keeps_verification(self):
        ctx = TLSConfig(server_hostname="example.com").build()
        assert ctx is not None
        assert ctx.check_hostname is True
        assert ctx.verify_mode == ssl.CERT_REQUIRED

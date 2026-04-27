"""TLS configuration helpers using Python's ssl module."""

from __future__ import annotations

import ssl
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TLSConfig:
    """TLS configuration dataclass with builder methods for ssl.SSLContext."""

    skip_verify: bool = False
    ca_file: str = ""
    cert_file: str = ""
    key_file: str = ""
    server_hostname: str = ""
    min_version: ssl.TLSVersion = ssl.TLSVersion.TLSv1_2

    def build(self) -> ssl.SSLContext | None:
        """Create a client-side ssl.SSLContext from config. Returns None if no settings configured."""
        if not self.is_enabled():
            return None

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = self.min_version

        if self.skip_verify:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        if self.ca_file:
            ctx.load_verify_locations(self.ca_file)

        if self.cert_file and self.key_file:
            ctx.load_cert_chain(self.cert_file, self.key_file)

        return ctx

    def build_server(self) -> ssl.SSLContext | None:
        """Create a server-side ssl.SSLContext (PROTOCOL_TLS_SERVER).

        Requires cert_file and key_file to be configured.
        """
        if not (self.cert_file and self.key_file):
            return None

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = self.min_version

        if self.ca_file:
            ctx.load_verify_locations(self.ca_file)
            ctx.verify_mode = ssl.CERT_REQUIRED

        if self.cert_file and self.key_file:
            ctx.load_cert_chain(self.cert_file, self.key_file)

        return ctx

    def validate(self) -> None:
        """Check config consistency. Raises ValueError or FileNotFoundError if invalid."""
        if bool(self.cert_file) != bool(self.key_file):
            raise ValueError("Both cert_file and key_file must be provided together")

        if self.ca_file and not Path(self.ca_file).exists():
            raise FileNotFoundError(f"CA file not found: {self.ca_file}")

        if self.cert_file and not Path(self.cert_file).exists():
            raise FileNotFoundError(f"Cert file not found: {self.cert_file}")

        if self.key_file and not Path(self.key_file).exists():
            raise FileNotFoundError(f"Key file not found: {self.key_file}")

    def is_enabled(self) -> bool:
        """Return True when any TLS-relevant option is configured."""
        return bool(self.skip_verify or self.ca_file or self.cert_file or self.server_hostname)

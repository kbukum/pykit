"""Signing key types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GPGSigningKey:
    """GPG signing key metadata."""

    key_id: str


@dataclass(frozen=True)
class SSHSigningKey:
    """SSH signing key metadata."""

    public_key_path: str

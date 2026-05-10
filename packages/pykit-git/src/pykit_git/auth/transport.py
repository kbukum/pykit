"""Transport authentication types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SSHKey:
    """SSH key credentials for git transport operations."""

    private_key_path: str
    username: str = "git"
    public_key_path: str | None = None
    passphrase: str | None = None


@dataclass(frozen=True)
class Token:
    """Token-based credentials for git transport operations."""

    value: str
    username: str = "oauth2"


@dataclass(frozen=True)
class BasicAuth:
    """Username and password credentials for git transport operations."""

    username: str
    password: str

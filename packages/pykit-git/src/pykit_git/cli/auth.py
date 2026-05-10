"""CLI auth helpers."""

from __future__ import annotations

import shlex
from collections.abc import Mapping

from pykit_git.auth.transport import BasicAuth, SSHKey, Token


def build_env(transport: BasicAuth | SSHKey | Token | None = None) -> Mapping[str, str]:
    """Return environment overrides for CLI auth support."""
    if transport is None:
        return {}
    if isinstance(transport, Token):
        return {
            "GIT_ASKPASS": "echo",
            "GIT_USERNAME": transport.username,
            "GIT_PASSWORD": transport.value,
        }
    if isinstance(transport, BasicAuth):
        return {
            "GIT_ASKPASS": "echo",
            "GIT_USERNAME": transport.username,
            "GIT_PASSWORD": transport.password,
        }
    command = ["ssh", "-i", transport.private_key_path]
    if transport.public_key_path:
        command.extend(["-o", f"CertificateFile={transport.public_key_path}"])
    return {"GIT_SSH_COMMAND": " ".join(shlex.quote(part) for part in command)}

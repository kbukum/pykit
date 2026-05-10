"""pygit2 credential wiring helpers."""

from __future__ import annotations

import pygit2

from pykit_git.auth.transport import BasicAuth, SSHKey, Token

Credential = SSHKey | Token | BasicAuth


def build_remote_callbacks(credential: Credential | None = None) -> pygit2.RemoteCallbacks | None:
    """Build pygit2 remote callbacks for an optional credential."""
    if credential is None:
        return None
    return pygit2.RemoteCallbacks(credentials=_credential_callback(credential))


def _credential_callback(
    credential: Credential,
):
    def callback(url: str, username_from_url: str | None, allowed_types: int):
        del url, username_from_url, allowed_types
        if isinstance(credential, Token):
            return pygit2.UserPass(credential.username, credential.value)
        if isinstance(credential, BasicAuth):
            return pygit2.UserPass(credential.username, credential.password)
        public_key = credential.public_key_path or ""
        passphrase = credential.passphrase or ""
        return pygit2.Keypair(credential.username, public_key, credential.private_key_path, passphrase)

    return callback

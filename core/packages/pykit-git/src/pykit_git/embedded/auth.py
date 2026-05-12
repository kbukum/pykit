"""pygit2 credential wiring helpers."""

from __future__ import annotations

from collections.abc import Callable

import pygit2

from pykit_git.auth.transport import BasicAuth, SSHKey, Token

Credential = SSHKey | Token | BasicAuth


def build_remote_callbacks(credential: Credential | None = None) -> pygit2.RemoteCallbacks | None:
    """Build pygit2 remote callbacks for an optional credential."""
    if credential is None:
        return None
    return pygit2.RemoteCallbacks(
        credentials=_credential_callback(credential)  # type: ignore[arg-type]
    )


def _credential_callback(
    credential: Credential,
) -> Callable[[str, str | None, int], pygit2.Keypair | pygit2.UserPass]:
    def callback(
        url: str, username_from_url: str | None, allowed_types: int
    ) -> pygit2.Keypair | pygit2.UserPass:
        del url, username_from_url
        if isinstance(credential, (Token, BasicAuth)):
            if not (allowed_types & pygit2.enums.CredentialType.USERPASS_PLAINTEXT):
                msg = "server does not accept username/password credentials"
                raise ValueError(msg)
            if isinstance(credential, Token):
                return pygit2.UserPass(credential.username, credential.value)
            return pygit2.UserPass(credential.username, credential.password)
        # SSHKey
        if not (allowed_types & pygit2.enums.CredentialType.SSH_KEY):
            msg = "server does not accept SSH key credentials"
            raise ValueError(msg)
        public_key = credential.public_key_path or ""
        passphrase = credential.passphrase or ""
        return pygit2.Keypair(credential.username, public_key, credential.private_key_path, passphrase)

    return callback

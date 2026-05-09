"""Skill signature verification policies."""

from __future__ import annotations

from pathlib import Path

from pykit_security.verifier import VerificationResult, Verifier

__all__ = ["DenyVerifier", "VerificationResult", "Verifier", "WarnOnlyVerifier"]


class WarnOnlyVerifier:
    """Default unsigned policy: warn, do not deny.

    Suitable for development. Operators SHOULD pair this with ``DenyVerifier``
    or a real signature verifier in production.
    """

    def verify(self, path: Path, signature: str | None) -> VerificationResult:
        if signature:
            return VerificationResult(trusted=True, reason="signature_present")
        return VerificationResult(trusted=True, reason=f"unsigned skill pack: {path}", warning=True)


class DenyVerifier:
    """Canonical operator-deny verifier: rejects every skill pack.

    Use as a safe default until a real signature verifier (e.g., Sigstore /
    cosign) adapter is wired in.
    """

    def verify(self, path: Path, signature: str | None) -> VerificationResult:
        return VerificationResult(trusted=False, reason="deny verifier: signatures rejected")

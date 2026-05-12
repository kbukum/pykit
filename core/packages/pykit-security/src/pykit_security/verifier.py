"""Generic signature verifier Protocol."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class VerificationResult:
    """Signature verification result."""

    trusted: bool
    reason: str
    warning: bool = False


@runtime_checkable
class Verifier(Protocol):
    """Verifier Protocol for signed artifacts such as skill packs."""

    def verify(self, path: Path, signature: str | None) -> VerificationResult:
        """Verify the artifact at ``path`` against the supplied signature."""

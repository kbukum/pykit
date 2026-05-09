"""Pure skill activation policy helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pykit_skill.manifest import Manifest, Safety

_ORDER = {Safety.READ_ONLY: 0, Safety.MUTATING: 1, Safety.DESTRUCTIVE: 2}


class EnvelopeLike(Protocol):
    """Structural view of a tool envelope without importing pykit-tool."""

    @property
    def scopes(self) -> tuple[str, ...]: ...

    @property
    def safety(self) -> Safety | str: ...


@dataclass(frozen=True, slots=True)
class EffectiveEnvelope:
    """Activation-time effective envelope summary."""

    tool: str
    scopes: tuple[str, ...]
    safety: Safety
    referenced: bool


def effective_safety(manifest: Manifest, declared: dict[str, EnvelopeLike]) -> Safety:
    """Return max safety over referenced tools; `manifest.safety` is informational."""
    safety = Safety.READ_ONLY
    for name in manifest.references.tools:
        env = declared.get(name)
        if env is None:
            continue
        candidate = Safety(str(env.safety))
        if _ORDER[candidate] > _ORDER[safety]:
            safety = candidate
    return safety


def effective_envelope(
    tool_name: str,
    manifest: Manifest,
    declared: EnvelopeLike,
    principal_grants: set[str],
    operator_ceiling: set[str],
) -> EffectiveEnvelope:
    """Apply T.declared ∩ principal.grants ∩ operator.ceiling ∩ skill.references."""
    referenced = tool_name in manifest.references.tools
    scopes = set(declared.scopes)
    if not referenced:
        scopes = set()
    scopes &= principal_grants
    scopes &= operator_ceiling
    return EffectiveEnvelope(
        tool=tool_name,
        scopes=tuple(sorted(scopes)),
        safety=Safety(str(declared.safety)),
        referenced=referenced,
    )

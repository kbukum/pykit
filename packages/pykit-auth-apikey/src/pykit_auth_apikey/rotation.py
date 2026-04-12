"""API key rotation with grace periods."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from pykit_auth_apikey.apikey import GenerateResult, generate, validate
from pykit_auth_apikey.store import Store

DEFAULT_GRACE_PERIOD = timedelta(days=7)


@dataclass(frozen=True)
class RotationConfig:
    """Configuration for key rotation."""

    grace_period: timedelta = DEFAULT_GRACE_PERIOD
    prefix: str = ""


@dataclass(frozen=True)
class RotationResult:
    """Outcome of a key rotation."""

    new_key: GenerateResult
    old_key_id: str
    grace_ends_at: datetime


async def rotate(store: Store, old_key_id: str, cfg: RotationConfig | None = None) -> RotationResult:
    """Generate a replacement key and set a grace period on the old one."""
    if cfg is None:
        cfg = RotationConfig()

    old_key = await store.get_by_id(old_key_id)
    validate(old_key)

    new_result = generate(cfg.prefix)
    grace_ends_at = datetime.now(UTC) + cfg.grace_period

    await store.set_grace_period(old_key_id, grace_ends_at, "")
    return RotationResult(new_key=new_result, old_key_id=old_key_id, grace_ends_at=grace_ends_at)

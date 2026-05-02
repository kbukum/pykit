"""API key issuance, validation, rotation, and ASGI middleware."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Protocol, cast, runtime_checkable

from pykit_errors import InvalidInputError

type Scope = dict[str, object]
type Receive = Callable[[], Awaitable[dict[str, object]]]
type Send = Callable[[dict[str, object]], Awaitable[None]]
type ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class APIKeyHashingConfig:
    """Configuration for API key hashing."""

    pepper: str
    entropy_bytes: int = 32

    def __post_init__(self) -> None:
        if len(self.pepper.encode("utf-8")) < 32:
            raise ValueError("pepper must be at least 32 bytes")
        if self.entropy_bytes < 16:
            raise ValueError("entropy_bytes must be at least 16")


@dataclass(frozen=True, slots=True)
class APIKeyRecord:
    """Persisted API key metadata."""

    id: str
    owner_id: str
    name: str
    key_prefix: str
    key_digest: str
    scopes: tuple[str, ...] = ()
    is_active: bool = True
    expires_at: datetime | None = None
    grace_ends_at: datetime | None = None
    rotated_by_id: str = ""
    last_used_at: datetime | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_usable(self, now: datetime | None = None) -> bool:
        """Return ``True`` when the key is active and not expired past grace."""

        current = now or datetime.now(UTC)
        if not self.is_active:
            return False
        if self.expires_at is None:
            return True
        if current <= self.expires_at:
            return True
        return self.grace_ends_at is not None and current <= self.grace_ends_at


@dataclass(frozen=True, slots=True)
class IssuedAPIKey:
    """Issued API key material shown once to the caller."""

    plain_key: str
    key_prefix: str
    key_digest: str

    def __repr__(self) -> str:
        return (
            f"IssuedAPIKey(plain_key='[REDACTED]', key_prefix={self.key_prefix!r}, key_digest='[REDACTED]')"
        )


@dataclass(frozen=True, slots=True)
class APIKeyRotationConfig:
    """API key rotation policy."""

    grace_period: timedelta = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class APIKeyRotationResult:
    """Result of rotating an API key."""

    issued: IssuedAPIKey
    record: APIKeyRecord
    grace_ends_at: datetime


class APIKeyValidationError(InvalidInputError):
    """Raised when an API key is missing, malformed, or invalid."""


@runtime_checkable
class APIKeyStore(Protocol):
    """Persistence contract for API keys."""

    async def create(self, key: APIKeyRecord) -> None: ...

    async def list_by_prefix(self, key_prefix: str) -> Sequence[APIKeyRecord]: ...

    async def get_by_id(self, key_id: str) -> APIKeyRecord: ...

    async def update_last_used(self, key_id: str, used_at: datetime) -> None: ...

    async def set_rotation(self, key_id: str, grace_ends_at: datetime, rotated_by_id: str) -> None: ...

    async def set_active(self, key_id: str, active: bool) -> None: ...


@runtime_checkable
class APIKeyValidator(Protocol):
    """Protocol used by API key middleware."""

    async def validate_key(self, plain_key: str, required_scopes: Sequence[str] = ()) -> APIKeyRecord: ...


def split_api_key(plain_key: str) -> tuple[str, str]:
    """Split *plain_key* into ``(prefix, secret)``."""

    prefix, separator, secret = plain_key.partition(".")
    if separator != "." or not prefix or not secret:
        raise APIKeyValidationError("invalid API key format")
    return prefix, secret


class APIKeyHasher:
    """Deterministic HMAC-SHA-256 hasher for API keys."""

    def __init__(self, config: APIKeyHashingConfig) -> None:
        self._config = config
        self._pepper = config.pepper.encode("utf-8")

    @property
    def config(self) -> APIKeyHashingConfig:
        """Return the active hashing configuration."""

        return self._config

    def generate_key(self, prefix: str) -> IssuedAPIKey:
        """Generate a new API key."""

        cleaned_prefix = self._validate_prefix(prefix)
        secret = secrets.token_urlsafe(self._config.entropy_bytes)
        plain_key = f"{cleaned_prefix}.{secret}"
        return IssuedAPIKey(
            plain_key=plain_key,
            key_prefix=cleaned_prefix,
            key_digest=self.digest(plain_key),
        )

    def digest(self, plain_key: str) -> str:
        """Digest *plain_key* with the configured pepper."""

        return hmac.new(self._pepper, plain_key.encode("utf-8"), hashlib.sha256).hexdigest()

    def compare(self, plain_key: str, stored_digest: str) -> bool:
        """Timing-safe comparison of *plain_key* against *stored_digest*."""

        candidate_digest = self.digest(plain_key)
        return hmac.compare_digest(candidate_digest, stored_digest)

    @staticmethod
    def _validate_prefix(prefix: str) -> str:
        if not prefix or any(
            char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in prefix
        ):
            raise ValueError("API key prefix must be non-empty and contain only [A-Za-z0-9_-]")
        return prefix


class APIKeyManager(APIKeyValidator):
    """Issue, validate, and rotate API keys using prefix-based lookup."""

    def __init__(self, store: APIKeyStore, hasher: APIKeyHasher) -> None:
        self._store = store
        self._hasher = hasher

    async def issue_key(
        self,
        *,
        key_id: str,
        owner_id: str,
        name: str,
        prefix: str,
        scopes: Sequence[str] = (),
        expires_at: datetime | None = None,
    ) -> tuple[IssuedAPIKey, APIKeyRecord]:
        """Issue and persist a new API key."""

        issued = self._hasher.generate_key(prefix)
        record = APIKeyRecord(
            id=key_id,
            owner_id=owner_id,
            name=name,
            key_prefix=issued.key_prefix,
            key_digest=issued.key_digest,
            scopes=tuple(scopes),
            expires_at=expires_at,
        )
        await self._store.create(record)
        return issued, record

    async def validate_key(self, plain_key: str, required_scopes: Sequence[str] = ()) -> APIKeyRecord:
        """Validate *plain_key* against the configured store."""

        key_prefix, _secret = split_api_key(plain_key)
        candidates = await self._store.list_by_prefix(key_prefix)
        matched_record: APIKeyRecord | None = None
        for candidate in candidates:
            digest_matches = self._hasher.compare(plain_key, candidate.key_digest)
            if digest_matches and matched_record is None:
                matched_record = candidate

        if matched_record is None:
            raise APIKeyValidationError("invalid API key")
        if not matched_record.is_usable():
            raise APIKeyValidationError("invalid API key")
        if required_scopes and not set(required_scopes).issubset(set(matched_record.scopes)):
            raise APIKeyValidationError("insufficient API key scope")

        used_at = datetime.now(UTC)
        await self._store.update_last_used(matched_record.id, used_at)
        return replace(matched_record, last_used_at=used_at)

    async def rotate_key(
        self,
        *,
        old_key_id: str,
        new_key_id: str,
        prefix: str,
        name: str,
        owner_id: str,
        scopes: Sequence[str] = (),
        expires_at: datetime | None = None,
        config: APIKeyRotationConfig | None = None,
    ) -> APIKeyRotationResult:
        """Rotate an API key and place the old key into a grace period."""

        rotation = config or APIKeyRotationConfig()
        old_record = await self._store.get_by_id(old_key_id)
        if not old_record.is_usable():
            raise APIKeyValidationError("invalid API key")

        issued, record = await self.issue_key(
            key_id=new_key_id,
            owner_id=owner_id,
            name=name,
            prefix=prefix,
            scopes=scopes or old_record.scopes,
            expires_at=expires_at,
        )
        grace_ends_at = datetime.now(UTC) + rotation.grace_period
        await self._store.set_rotation(old_key_id, grace_ends_at, record.id)
        return APIKeyRotationResult(issued=issued, record=record, grace_ends_at=grace_ends_at)


class APIKeyMiddleware:
    """ASGI middleware that accepts missing credentials but rejects invalid ones."""

    def __init__(
        self,
        app: ASGIApp,
        validator: APIKeyValidator,
        *,
        header_name: str = "x-api-key",
        required_scopes: Sequence[str] = (),
    ) -> None:
        self._app = app
        self._validator = validator
        self._header_name = header_name.lower().encode("latin-1")
        self._required_scopes = tuple(required_scopes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http":
            await self._app(scope, receive, send)
            return

        raw_headers = cast("Sequence[tuple[bytes, bytes]]", scope.get("headers", ()))
        headers = {key.lower(): value for key, value in raw_headers}
        if b"access_token" in headers or b"token" in headers:
            await self._unauthorized(send)
            return

        raw_key = headers.get(self._header_name)
        if raw_key is None:
            await self._app(scope, receive, send)
            return

        try:
            record = await self._validator.validate_key(raw_key.decode("latin-1"), self._required_scopes)
        except InvalidInputError:
            await self._unauthorized(send)
            return

        state = scope.setdefault("state", {})
        if not isinstance(state, dict):
            raise APIKeyValidationError("ASGI state must be a mutable mapping")
        state["auth.apikey"] = record
        state["auth.subject"] = record.owner_id
        await self._app(scope, receive, send)

    @staticmethod
    async def _unauthorized(send: Send) -> None:
        body = json.dumps({"error": "invalid or expired API key"}).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode("ascii")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})

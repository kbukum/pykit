"""Tests for bundled API key support."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from pykit_auth import (
    APIKeyHasher,
    APIKeyHashingConfig,
    APIKeyManager,
    APIKeyMiddleware,
    APIKeyRecord,
    APIKeyRotationConfig,
    APIKeyValidationError,
    split_api_key,
)


class InMemoryStore:
    def __init__(self) -> None:
        self.records: dict[str, APIKeyRecord] = {}

    async def create(self, key: APIKeyRecord) -> None:
        self.records[key.id] = key

    async def list_by_prefix(self, key_prefix: str) -> list[APIKeyRecord]:
        return [record for record in self.records.values() if record.key_prefix == key_prefix]

    async def get_by_id(self, key_id: str) -> APIKeyRecord:
        return self.records[key_id]

    async def update_last_used(self, key_id: str, used_at: datetime) -> None:
        self.records[key_id] = replace(self.records[key_id], last_used_at=used_at)

    async def set_rotation(self, key_id: str, grace_ends_at: datetime, rotated_by_id: str) -> None:
        record = self.records[key_id]
        self.records[key_id] = replace(record, grace_ends_at=grace_ends_at, rotated_by_id=rotated_by_id)

    async def set_active(self, key_id: str, active: bool) -> None:
        record = self.records[key_id]
        self.records[key_id] = replace(record, is_active=active)


@pytest.mark.asyncio
class TestAPIKeyManager:
    async def test_issue_validate_and_rotate(self) -> None:
        manager = APIKeyManager(InMemoryStore(), APIKeyHasher(APIKeyHashingConfig(pepper="p" * 32)))
        issued, _record = await manager.issue_key(
            key_id="key-1",
            owner_id="user-1",
            name="primary",
            prefix="pk",
            scopes=("read", "write"),
        )

        validated = await manager.validate_key(issued.plain_key, required_scopes=("read",))
        assert validated.owner_id == "user-1"
        assert validated.last_used_at is not None

        rotation = await manager.rotate_key(
            old_key_id="key-1",
            new_key_id="key-2",
            prefix="pk",
            name="secondary",
            owner_id="user-1",
            scopes=("read", "write"),
            config=APIKeyRotationConfig(grace_period=timedelta(hours=1)),
        )

        assert rotation.record.id == "key-2"
        assert rotation.grace_ends_at > datetime.now(UTC)
        rotated_record = await manager._store.get_by_id("key-1")
        assert rotated_record.rotated_by_id == "key-2"

    async def test_validation_rejects_scope_escalation(self) -> None:
        manager = APIKeyManager(InMemoryStore(), APIKeyHasher(APIKeyHashingConfig(pepper="p" * 32)))
        issued, _record = await manager.issue_key(
            key_id="key-1",
            owner_id="user-1",
            name="primary",
            prefix="pk",
            scopes=("read",),
        )

        with pytest.raises(APIKeyValidationError, match="scope"):
            await manager.validate_key(issued.plain_key, required_scopes=("write",))

    async def test_validation_rejects_expired_keys(self) -> None:
        store = InMemoryStore()
        hasher = APIKeyHasher(APIKeyHashingConfig(pepper="p" * 32))
        manager = APIKeyManager(store, hasher)
        issued = hasher.generate_key("pk")
        await store.create(
            APIKeyRecord(
                id="key-1",
                owner_id="user-1",
                name="expired",
                key_prefix=issued.key_prefix,
                key_digest=issued.key_digest,
                expires_at=datetime.now(UTC) - timedelta(minutes=5),
            )
        )

        with pytest.raises(APIKeyValidationError, match="invalid API key"):
            await manager.validate_key(issued.plain_key)


class TestAPIKeyHelpers:
    def test_split_api_key_requires_prefix(self) -> None:
        prefix, secret = split_api_key("pk.secret")
        assert prefix == "pk"
        assert secret == "secret"

        with pytest.raises(APIKeyValidationError):
            split_api_key("malformed")

    def test_digest_uses_constant_time_compare(self) -> None:
        hasher = APIKeyHasher(APIKeyHashingConfig(pepper="p" * 32))
        issued = hasher.generate_key("pk")
        with patch("pykit_auth.apikey.hmac.compare_digest", return_value=True) as compare_digest:
            hasher.compare(issued.plain_key, issued.key_digest)
        compare_digest.assert_called_once()

    def test_plaintext_key_repr_is_redacted(self) -> None:
        issued = APIKeyHasher(APIKeyHashingConfig(pepper="p" * 32)).generate_key("pk")
        assert issued.plain_key not in repr(issued)

    def test_hashing_config_and_prefix_validation(self) -> None:
        with pytest.raises(ValueError, match="32 bytes"):
            APIKeyHashingConfig(pepper="short")

        hasher = APIKeyHasher(APIKeyHashingConfig(pepper="p" * 32))
        with pytest.raises(ValueError, match="prefix"):
            hasher.generate_key("bad prefix")


@pytest.mark.asyncio
async def test_apikey_middleware_accepts_missing_and_rejects_invalid() -> None:
    async def app(scope, receive, send):  # type: ignore[no-untyped-def]
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    class RejectingValidator:
        async def validate_key(self, plain_key: str, required_scopes=()):  # type: ignore[no-untyped-def]
            raise APIKeyValidationError("invalid")

    calls: list[dict[str, object]] = []

    async def send(message: dict[str, object]) -> None:
        calls.append(message)

    middleware = APIKeyMiddleware(app, RejectingValidator())
    await middleware(
        {"type": "http", "headers": [(b"x-api-key", b"pk.invalid")]},
        lambda: None,  # type: ignore[arg-type]
        send,
    )

    assert calls[0]["status"] == 401


@pytest.mark.asyncio
async def test_apikey_middleware_passes_through_non_http_and_missing_keys() -> None:
    calls: list[dict[str, object]] = []

    async def app(scope, receive, send):  # type: ignore[no-untyped-def]
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    class AcceptingValidator:
        async def validate_key(self, plain_key: str, required_scopes=()):  # type: ignore[no-untyped-def]
            raise AssertionError("validator should not be called")

    async def send(message: dict[str, object]) -> None:
        calls.append(message)

    middleware = APIKeyMiddleware(app, AcceptingValidator())
    await middleware({"type": "websocket"}, lambda: None, send)  # type: ignore[arg-type]
    await middleware({"type": "http", "headers": []}, lambda: None, send)  # type: ignore[arg-type]

    assert calls[0]["status"] == 204
    assert calls[2]["status"] == 204

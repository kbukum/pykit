"""Tests for JsonTranslator serialize/deserialize."""

from __future__ import annotations

from pykit_messaging.translator import JsonTranslator, MessageTranslator


class TestJsonTranslator:
    def test_serialize(self) -> None:
        t = JsonTranslator()
        result = t.serialize({"key": "value", "number": 42})
        assert isinstance(result, bytes)
        assert b'"key"' in result
        assert b'"value"' in result

    def test_deserialize(self) -> None:
        t = JsonTranslator()
        data = t.deserialize(b'{"key": "value", "number": 42}')
        assert data == {"key": "value", "number": 42}

    def test_roundtrip(self) -> None:
        t = JsonTranslator()
        original = {"name": "Alice", "age": 30, "items": [1, 2, 3]}
        raw = t.serialize(original)
        restored = t.deserialize(raw)
        assert restored == original

    def test_serialize_with_special_types(self) -> None:
        """Non-serializable types use str() via default=str."""
        from datetime import UTC, datetime

        t = JsonTranslator()
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)
        result = t.serialize({"timestamp": dt})
        assert isinstance(result, bytes)
        restored = t.deserialize(result)
        assert "2024-01-15" in restored["timestamp"]

    def test_satisfies_protocol(self) -> None:
        t = JsonTranslator()
        assert isinstance(t, MessageTranslator)

    def test_empty_dict(self) -> None:
        t = JsonTranslator()
        raw = t.serialize({})
        assert t.deserialize(raw) == {}

    def test_nested_dict(self) -> None:
        t = JsonTranslator()
        original = {"outer": {"inner": {"deep": True}}}
        assert t.deserialize(t.serialize(original)) == original

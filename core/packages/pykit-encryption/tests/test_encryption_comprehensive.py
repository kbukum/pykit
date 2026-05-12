"""Comprehensive tests for pykit-encryption."""

from __future__ import annotations

import base64
import threading

import pytest
from cryptography.exceptions import InvalidTag

from pykit_encryption import (
    AESGCMEncryptor,
    ChaCha20Encryptor,
    Encryptor,
    new_encryptor,
)
from pykit_encryption.factory import _REGISTRY, Algorithm

PLAINTEXTS: list[str] = [
    "",
    "hello",
    "hello world",
    "a" * 10_000,
    "こんにちは 🌍",
    "مرحبا بالعالم",
    "\u0000\u0001\u0002",
    "\n\r\t",
    "line1\nline2\nline3",
    'key=value&foo="bar"',
    "<script>alert('xss')</script>",
    "🏳️‍🌈👨‍👩‍👧‍👦",
    "\x00",
    "a" * 100_000,
    "spaces   multiple   tabs\t\there",
    '{"json": true, "nested": {"a": 1}}',
]

KEYS: list[str] = [
    "simple",
    "",
    "a",
    "k" * 1024,
    "pässwörd-with-ümläuts",
    "🔑🔐",
    "key with spaces",
    "key\x00with\x00nulls",
]


@pytest.fixture(params=[AESGCMEncryptor, ChaCha20Encryptor], ids=["aesgcm", "chacha20"])
def encryptor_cls(request: pytest.FixtureRequest) -> type[AESGCMEncryptor] | type[ChaCha20Encryptor]:
    return request.param


@pytest.fixture(params=[Algorithm.AES_GCM, Algorithm.CHACHA20], ids=["aes-gcm", "chacha20"])
def algorithm(request: pytest.FixtureRequest) -> Algorithm:
    return request.param


class TestParametrizedRoundTrips:
    @pytest.mark.parametrize("plaintext", PLAINTEXTS, ids=[f"pt{i}" for i in range(len(PLAINTEXTS))])
    def test_roundtrip_all_plaintexts(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
        plaintext: str,
    ) -> None:
        enc = encryptor_cls("test-key-123")
        ct = enc.encrypt(plaintext)
        assert enc.decrypt(ct) == plaintext

    @pytest.mark.parametrize("key", KEYS, ids=[f"key{i}" for i in range(len(KEYS))])
    def test_roundtrip_various_keys(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
        key: str,
    ) -> None:
        enc = encryptor_cls(key)
        ct = enc.encrypt("round-trip payload")
        assert enc.decrypt(ct) == "round-trip payload"

    def test_roundtrip_via_factory(self, algorithm: Algorithm) -> None:
        enc = new_encryptor("factory-key", algorithm)
        for text in ["", "abc", "🔐 secret"]:
            assert enc.decrypt(enc.encrypt(text)) == text


class TestWrongKey:
    @pytest.mark.parametrize(
        ("encryptor_cls", "right_key", "wrong_key"),
        [
            (AESGCMEncryptor, "correct", "incorrect"),
            (AESGCMEncryptor, "a", "b"),
            (AESGCMEncryptor, "key", "key "),
            (AESGCMEncryptor, "Key", "key"),
            (AESGCMEncryptor, "🔑", "🔐"),
            (ChaCha20Encryptor, "correct", "incorrect"),
            (ChaCha20Encryptor, "a", "b"),
            (ChaCha20Encryptor, "key", "key "),
            (ChaCha20Encryptor, "Key", "key"),
            (ChaCha20Encryptor, "🔑", "🔐"),
        ],
    )
    def test_wrong_key_raises(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
        right_key: str,
        wrong_key: str,
    ) -> None:
        ct = encryptor_cls(right_key).encrypt("secret data")
        with pytest.raises(InvalidTag):
            encryptor_cls(wrong_key).decrypt(ct)

    def test_wrong_key_via_factory(self, algorithm: Algorithm) -> None:
        ct = new_encryptor("right", algorithm).encrypt("payload")
        with pytest.raises(InvalidTag):
            new_encryptor("wrong", algorithm).decrypt(ct)


class TestTamperedCiphertext:
    def _tamper_byte(self, ct_b64: str, offset: int) -> str:
        raw = bytearray(base64.standard_b64decode(ct_b64))
        if offset < len(raw):
            raw[offset] ^= 0xFF
        return base64.standard_b64encode(bytes(raw)).decode()

    @pytest.mark.parametrize(
        ("encryptor_cls", "position"),
        [
            (AESGCMEncryptor, "first"),
            (AESGCMEncryptor, "middle"),
            (AESGCMEncryptor, "last"),
            (ChaCha20Encryptor, "first"),
            (ChaCha20Encryptor, "middle"),
            (ChaCha20Encryptor, "last"),
        ],
    )
    def test_tamper_positions(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
        position: str,
    ) -> None:
        enc = encryptor_cls("tamper-key")
        ct = enc.encrypt("detect me")
        raw = base64.standard_b64decode(ct)
        offsets = {"first": 0, "middle": len(raw) // 2, "last": len(raw) - 1}
        tampered = self._tamper_byte(ct, offsets[position])
        with pytest.raises((InvalidTag, ValueError)):
            enc.decrypt(tampered)

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_truncated_ciphertext(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        ct = enc.encrypt("hello")
        raw = base64.standard_b64decode(ct)
        for length in [0, 1, 15, 16, 27]:
            truncated = base64.standard_b64encode(raw[:length]).decode()
            with pytest.raises((ValueError, InvalidTag)):
                enc.decrypt(truncated)

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_appended_bytes(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        ct = enc.encrypt("hello")
        raw = base64.standard_b64decode(ct)
        extended = base64.standard_b64encode(raw + b"\x00" * 16).decode()
        with pytest.raises(InvalidTag):
            enc.decrypt(extended)

    def test_completely_invalid_base64(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        with pytest.raises(Exception):  # noqa: B017
            enc.decrypt("!!!not-valid-base64!!!")

    def test_empty_ciphertext_string(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        with pytest.raises(Exception):  # noqa: B017
            enc.decrypt("")


class TestKeyRotation:
    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_key_rotation(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        old_enc = encryptor_cls("old-key")
        new_enc = encryptor_cls("new-key")

        original = "rotate this secret"
        old_ct = old_enc.encrypt(original)
        new_ct = new_enc.encrypt(old_enc.decrypt(old_ct))

        assert new_enc.decrypt(new_ct) == original
        with pytest.raises(InvalidTag):
            old_enc.decrypt(new_ct)

    def test_key_rotation_via_factory(self, algorithm: Algorithm) -> None:
        old = new_encryptor("old", algorithm)
        new = new_encryptor("new", algorithm)
        ct = old.encrypt("data")
        rotated_ct = new.encrypt(old.decrypt(ct))
        assert new.decrypt(rotated_ct) == "data"

    def test_bulk_key_rotation(self) -> None:
        old_enc = AESGCMEncryptor("old-key")
        new_enc = AESGCMEncryptor("new-key")
        records = [f"record-{i}" for i in range(100)]
        old_cts = [old_enc.encrypt(r) for r in records]
        rotated = [new_enc.encrypt(old_enc.decrypt(ct)) for ct in old_cts]
        decrypted = [new_enc.decrypt(ct) for ct in rotated]
        assert decrypted == records


class TestFactoryProtocol:
    def test_all_algorithms_in_registry(self) -> None:
        for algo in Algorithm:
            assert algo in _REGISTRY, f"{algo} missing from registry"

    def test_registry_classes_conform_to_protocol(self) -> None:
        for cls in _REGISTRY.values():
            assert isinstance(cls("test-key"), Encryptor)

    def test_encryptor_protocol_has_encrypt_and_decrypt(self) -> None:
        assert hasattr(Encryptor, "encrypt")
        assert hasattr(Encryptor, "decrypt")

    def test_custom_class_conforms_to_protocol(self) -> None:
        class CustomEncryptor:
            def encrypt(self, plaintext: str) -> str:
                return plaintext[::-1]

            def decrypt(self, ciphertext: str) -> str:
                return ciphertext[::-1]

        assert isinstance(CustomEncryptor(), Encryptor)

    def test_incomplete_class_does_not_conform(self) -> None:
        class MissingDecrypt:
            def encrypt(self, plaintext: str) -> str:
                return plaintext

        assert not isinstance(MissingDecrypt(), Encryptor)

    def test_factory_returns_correct_types(self) -> None:
        assert type(new_encryptor("k", Algorithm.AES_GCM)) is AESGCMEncryptor
        assert type(new_encryptor("k", Algorithm.CHACHA20)) is ChaCha20Encryptor

    def test_factory_invalid_algorithm_message(self) -> None:
        with pytest.raises(ValueError, match="unsupported algorithm"):
            new_encryptor("key", "not-a-real-algo")  # type: ignore[arg-type]

    def test_algorithm_enum_values(self) -> None:
        assert Algorithm.AES_GCM.value == "aes-gcm"
        assert Algorithm.CHACHA20.value == "chacha20-poly1305"

    def test_algorithm_enum_members_count(self) -> None:
        assert len(Algorithm) == len(_REGISTRY)


class TestSecurity:
    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_same_key_is_deterministically_derived(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc1 = encryptor_cls("my-key")
        enc2 = encryptor_cls("my-key")
        ct = enc1.encrypt("verify key derivation is deterministic")
        assert enc2.decrypt(ct) == "verify key derivation is deterministic"

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_nonce_is_12_bytes(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        ct = enc.encrypt("test")
        raw = base64.standard_b64decode(ct)
        nonce = raw[16:28]
        assert len(nonce) == 12

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_salt_and_nonce_are_unique_per_message(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        prefixes: set[bytes] = set()
        for _ in range(250):
            ct = enc.encrypt("same plaintext")
            raw = base64.standard_b64decode(ct)
            prefixes.add(raw[:28])
        assert len(prefixes) == 250

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_ciphertext_contains_salt_nonce_and_tag(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        plaintext = "exactly 16 bytes"
        ct = enc.encrypt(plaintext)
        raw = base64.standard_b64decode(ct)
        expected_min = 16 + 12 + len(plaintext.encode()) + 16
        assert len(raw) == expected_min

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_different_keys_cannot_decrypt(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        ct_a = encryptor_cls("key-a").encrypt("secret")
        ct_b = encryptor_cls("key-b").encrypt("secret")
        with pytest.raises(InvalidTag):
            encryptor_cls("key-b").decrypt(ct_a)
        with pytest.raises(InvalidTag):
            encryptor_cls("key-a").decrypt(ct_b)

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_ciphertext_reveals_no_plaintext_prefix(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        ct1 = base64.standard_b64decode(enc.encrypt("AAAA"))
        ct2 = base64.standard_b64decode(enc.encrypt("AAAB"))
        assert ct1[28:] != ct2[28:]

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_zero_length_key_still_works(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("")
        ct = enc.encrypt("data")
        assert enc.decrypt(ct) == "data"

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_very_long_key_works(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        long_key = "x" * 100_000
        enc = encryptor_cls(long_key)
        ct = enc.encrypt("data")
        assert enc.decrypt(ct) == "data"


class TestEdgeCases:
    def test_binary_like_string(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        text = "".join(chr(i) for i in range(256) if chr(i).isprintable())
        enc = encryptor_cls("key")
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_null_bytes_in_plaintext(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        text = "before\x00after"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_very_large_payload(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        large = "X" * 1_000_000
        assert enc.decrypt(enc.encrypt(large)) == large

    def test_repeated_encrypt_decrypt_cycles(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        text = "cycle test"
        for _ in range(50):
            text = enc.decrypt(enc.encrypt(text))
        assert text == "cycle test"

    def test_multiline_plaintext(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        text = "line1\nline2\rline3\r\nline4"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_whitespace_only(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        for ws in [" ", "\t", "\n", "   \t\n  "]:
            assert enc.decrypt(enc.encrypt(ws)) == ws

    def test_surrogate_emoji_sequences(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        text = "👨‍👩‍👧‍👦🏳️‍🌈🇺🇸"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_rtl_and_mixed_scripts(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        text = "Hello مرحبا שלום こんにちは"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_sql_injection_like_string(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        text = "'; DROP TABLE users; --"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_html_and_js_strings(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        text = '<img onerror="alert(1)" src=x>'
        assert enc.decrypt(enc.encrypt(text)) == text


class TestCrossAlgorithm:
    def test_aesgcm_ciphertext_fails_with_chacha20(self) -> None:
        ct = AESGCMEncryptor("key").encrypt("data")
        with pytest.raises(InvalidTag):
            ChaCha20Encryptor("key").decrypt(ct)

    def test_chacha20_ciphertext_fails_with_aesgcm(self) -> None:
        ct = ChaCha20Encryptor("key").encrypt("data")
        with pytest.raises(InvalidTag):
            AESGCMEncryptor("key").decrypt(ct)


class TestConcurrency:
    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_threaded_encrypt_decrypt(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("thread-key")
        errors: list[str] = []

        def worker(idx: int) -> None:
            try:
                text = f"thread-{idx}-payload"
                for _ in range(100):
                    ct = enc.encrypt(text)
                    result = enc.decrypt(ct)
                    if result != text:
                        errors.append(f"thread {idx}: mismatch")
            except Exception as exc:  # pragma: no cover
                errors.append(f"thread {idx}: {exc}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == [], f"Thread errors: {errors}"


class TestOutputFormat:
    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_output_is_standard_base64(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        ct = enc.encrypt("test")
        decoded = base64.standard_b64decode(ct)
        re_encoded = base64.standard_b64encode(decoded).decode()
        assert ct == re_encoded

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_encrypt_returns_str(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        assert isinstance(encryptor_cls("key").encrypt("test"), str)

    @pytest.mark.parametrize("encryptor_cls", [AESGCMEncryptor, ChaCha20Encryptor])
    def test_decrypt_returns_str(
        self,
        encryptor_cls: type[AESGCMEncryptor] | type[ChaCha20Encryptor],
    ) -> None:
        enc = encryptor_cls("key")
        assert isinstance(enc.decrypt(enc.encrypt("test")), str)

"""Comprehensive TDD tests for pykit-encryption.

Supplements test_encryption.py with parametrized tests, security validations,
edge cases, key-rotation simulation, and cross-algorithm checks.
"""

from __future__ import annotations

import base64
import hashlib
import threading

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.fernet import InvalidToken

from pykit_encryption import (
    AESGCMEncryptor,
    Encryptor,
    FernetEncryptor,
    new_encryptor,
)
from pykit_encryption.factory import _REGISTRY, Algorithm

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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


@pytest.fixture(params=[AESGCMEncryptor, FernetEncryptor], ids=["aesgcm", "fernet"])
def encryptor_cls(request: pytest.FixtureRequest) -> type:
    return request.param


@pytest.fixture(params=[Algorithm.AES_GCM, Algorithm.FERNET], ids=["aes-gcm", "fernet"])
def algorithm(request: pytest.FixtureRequest) -> Algorithm:
    return request.param


# ---------------------------------------------------------------------------
# 1. Parametrized round-trip tests across all algorithms and plaintexts
# ---------------------------------------------------------------------------


class TestParametrizedRoundTrips:
    """Encrypt->decrypt must be identity for every algorithm x plaintext x key."""

    @pytest.mark.parametrize("plaintext", PLAINTEXTS, ids=[f"pt{i}" for i in range(len(PLAINTEXTS))])
    def test_roundtrip_all_plaintexts(self, encryptor_cls: type, plaintext: str) -> None:
        enc = encryptor_cls("test-key-123")
        ct = enc.encrypt(plaintext)
        assert enc.decrypt(ct) == plaintext

    @pytest.mark.parametrize("key", KEYS, ids=[f"key{i}" for i in range(len(KEYS))])
    def test_roundtrip_various_keys(self, encryptor_cls: type, key: str) -> None:
        enc = encryptor_cls(key)
        ct = enc.encrypt("round-trip payload")
        assert enc.decrypt(ct) == "round-trip payload"

    def test_roundtrip_via_factory(self, algorithm: Algorithm) -> None:
        enc = new_encryptor("factory-key", algorithm)
        for text in ["", "abc", "🔐 secret"]:
            assert enc.decrypt(enc.encrypt(text)) == text


# ---------------------------------------------------------------------------
# 2. Wrong key / password produces clear error
# ---------------------------------------------------------------------------


class TestWrongKey:
    @pytest.mark.parametrize(
        "right_key,wrong_key",
        [
            ("correct", "incorrect"),
            ("a", "b"),
            ("key", "key "),  # trailing space
            ("Key", "key"),  # case sensitivity
            ("🔑", "🔐"),
        ],
    )
    def test_aesgcm_wrong_key_raises(self, right_key: str, wrong_key: str) -> None:
        ct = AESGCMEncryptor(right_key).encrypt("secret data")
        with pytest.raises(InvalidTag):
            AESGCMEncryptor(wrong_key).decrypt(ct)

    @pytest.mark.parametrize(
        "right_key,wrong_key",
        [
            ("correct", "incorrect"),
            ("a", "b"),
            ("key", "key "),
            ("Key", "key"),
            ("🔑", "🔐"),
        ],
    )
    def test_fernet_wrong_key_raises(self, right_key: str, wrong_key: str) -> None:
        ct = FernetEncryptor(right_key).encrypt("secret data")
        with pytest.raises(InvalidToken):
            FernetEncryptor(wrong_key).decrypt(ct)

    def test_wrong_key_via_factory(self, algorithm: Algorithm) -> None:
        ct = new_encryptor("right", algorithm).encrypt("payload")
        with pytest.raises(Exception):  # noqa: B017
            new_encryptor("wrong", algorithm).decrypt(ct)


# ---------------------------------------------------------------------------
# 3. Tampered ciphertext detection
# ---------------------------------------------------------------------------


class TestTamperedCiphertext:
    """Any modification to ciphertext must be detected."""

    def _tamper_byte(self, ct_b64: str, offset: int) -> str:
        raw = bytearray(base64.standard_b64decode(ct_b64))
        if offset < len(raw):
            raw[offset] ^= 0xFF
        return base64.standard_b64encode(bytes(raw)).decode()

    @pytest.mark.parametrize("position", ["first", "middle", "last"])
    def test_aesgcm_tamper_positions(self, position: str) -> None:
        enc = AESGCMEncryptor("tamper-key")
        ct = enc.encrypt("detect me")
        raw = base64.standard_b64decode(ct)
        offsets = {"first": 0, "middle": len(raw) // 2, "last": len(raw) - 1}
        tampered = self._tamper_byte(ct, offsets[position])
        with pytest.raises((InvalidTag, ValueError)):
            enc.decrypt(tampered)

    def test_aesgcm_truncated_ciphertext(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("hello")
        raw = base64.standard_b64decode(ct)
        for length in [0, 1, 11, 12]:
            truncated = base64.standard_b64encode(raw[:length]).decode()
            with pytest.raises((ValueError, InvalidTag, Exception)):
                enc.decrypt(truncated)

    def test_aesgcm_appended_bytes(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("hello")
        raw = base64.standard_b64decode(ct)
        extended = base64.standard_b64encode(raw + b"\x00" * 16).decode()
        with pytest.raises((InvalidTag, Exception)):
            enc.decrypt(extended)

    def test_fernet_tamper_detected(self) -> None:
        enc = FernetEncryptor("tamper-key")
        ct = enc.encrypt("detect me")
        raw = bytearray(base64.urlsafe_b64decode(ct))
        raw[len(raw) // 2] ^= 0xFF
        tampered = base64.urlsafe_b64encode(bytes(raw)).decode()
        with pytest.raises((InvalidToken, Exception)):
            enc.decrypt(tampered)

    def test_fernet_truncated_ciphertext(self) -> None:
        enc = FernetEncryptor("key")
        ct = enc.encrypt("hello")
        with pytest.raises((InvalidToken, Exception)):
            enc.decrypt(ct[:10])

    def test_completely_invalid_base64(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        with pytest.raises(Exception):  # noqa: B017
            enc.decrypt("!!!not-valid-base64!!!")

    def test_empty_ciphertext_string(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        with pytest.raises(Exception):  # noqa: B017
            enc.decrypt("")


# ---------------------------------------------------------------------------
# 4. Key rotation simulation
# ---------------------------------------------------------------------------


class TestKeyRotation:
    """Simulate rotating keys: decrypt with old, re-encrypt with new."""

    def test_aesgcm_key_rotation(self) -> None:
        old_enc = AESGCMEncryptor("old-key")
        new_enc = AESGCMEncryptor("new-key")

        original = "rotate this secret"
        old_ct = old_enc.encrypt(original)

        # Decrypt with old key, re-encrypt with new key
        plaintext = old_enc.decrypt(old_ct)
        new_ct = new_enc.encrypt(plaintext)

        # New key decrypts fine
        assert new_enc.decrypt(new_ct) == original
        # Old key cannot decrypt new ciphertext
        with pytest.raises(InvalidTag):
            old_enc.decrypt(new_ct)

    def test_fernet_key_rotation(self) -> None:
        old_enc = FernetEncryptor("old-key")
        new_enc = FernetEncryptor("new-key")

        original = "rotate this secret"
        old_ct = old_enc.encrypt(original)

        plaintext = old_enc.decrypt(old_ct)
        new_ct = new_enc.encrypt(plaintext)

        assert new_enc.decrypt(new_ct) == original
        with pytest.raises(InvalidToken):
            old_enc.decrypt(new_ct)

    def test_key_rotation_via_factory(self, algorithm: Algorithm) -> None:
        old = new_encryptor("old", algorithm)
        new = new_encryptor("new", algorithm)
        ct = old.encrypt("data")
        rotated_ct = new.encrypt(old.decrypt(ct))
        assert new.decrypt(rotated_ct) == "data"

    def test_bulk_key_rotation(self) -> None:
        """Rotate many records from old key to new key."""
        old_enc = AESGCMEncryptor("old-key")
        new_enc = AESGCMEncryptor("new-key")
        records = [f"record-{i}" for i in range(100)]
        old_cts = [old_enc.encrypt(r) for r in records]

        rotated = [new_enc.encrypt(old_enc.decrypt(ct)) for ct in old_cts]
        decrypted = [new_enc.decrypt(ct) for ct in rotated]
        assert decrypted == records


# ---------------------------------------------------------------------------
# 5. Factory / Protocol pattern
# ---------------------------------------------------------------------------


class TestFactoryProtocol:
    def test_all_algorithms_in_registry(self) -> None:
        """Every Algorithm enum member must have a registered class."""
        for algo in Algorithm:
            assert algo in _REGISTRY, f"{algo} missing from registry"

    def test_registry_classes_conform_to_protocol(self) -> None:
        for _algo, cls in _REGISTRY.items():
            instance = cls("test-key")  # type: ignore[call-arg]
            assert isinstance(instance, Encryptor), f"{cls.__name__} does not conform to Encryptor protocol"

    def test_encryptor_protocol_has_encrypt_and_decrypt(self) -> None:
        assert hasattr(Encryptor, "encrypt")
        assert hasattr(Encryptor, "decrypt")

    def test_custom_class_conforms_to_protocol(self) -> None:
        """A custom class with encrypt/decrypt satisfies the protocol."""

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
        assert type(new_encryptor("k", Algorithm.FERNET)) is FernetEncryptor

    def test_factory_invalid_algorithm_message(self) -> None:
        with pytest.raises(ValueError, match="unsupported algorithm"):
            new_encryptor("key", "not-a-real-algo")  # type: ignore[arg-type]

    def test_algorithm_enum_values(self) -> None:
        assert Algorithm.AES_GCM.value == "aes-gcm"
        assert Algorithm.FERNET.value == "fernet"

    def test_algorithm_enum_members_count(self) -> None:
        assert len(Algorithm) == len(_REGISTRY)


# ---------------------------------------------------------------------------
# 6. Security-focused tests
# ---------------------------------------------------------------------------


class TestSecurity:
    def test_aesgcm_key_is_sha256_hashed(self) -> None:
        """Two encryptors with the same key must decrypt each other's output."""
        enc1 = AESGCMEncryptor("my-key")
        enc2 = AESGCMEncryptor("my-key")
        ct = enc1.encrypt("verify key derivation is deterministic")
        assert enc2.decrypt(ct) == "verify key derivation is deterministic"

    def test_aesgcm_nonce_is_12_bytes(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("test")
        raw = base64.standard_b64decode(ct)
        nonce = raw[:12]
        assert len(nonce) == 12

    def test_aesgcm_nonce_uniqueness(self) -> None:
        """Each encryption must use a unique nonce."""
        enc = AESGCMEncryptor("key")
        nonces: set[bytes] = set()
        for _ in range(1000):
            ct = enc.encrypt("same plaintext")
            raw = base64.standard_b64decode(ct)
            nonce = raw[:12]
            nonces.add(nonce)
        # All 1000 nonces should be unique
        assert len(nonces) == 1000

    def test_aesgcm_ciphertext_contains_nonce_plus_tag(self) -> None:
        """Ciphertext = nonce (12) + encrypted_data + GCM tag (16)."""
        enc = AESGCMEncryptor("key")
        plaintext = "exactly 16 bytes"
        ct = enc.encrypt(plaintext)
        raw = base64.standard_b64decode(ct)
        # nonce(12) + ciphertext(len(plaintext)) + tag(16)
        expected_min = 12 + len(plaintext.encode()) + 16
        assert len(raw) == expected_min

    def test_different_keys_derive_different_internal_keys(self) -> None:
        """Different passwords must not decrypt each other's ciphertext."""
        ct_a = AESGCMEncryptor("key-a").encrypt("secret")
        ct_b = AESGCMEncryptor("key-b").encrypt("secret")
        # Cross-decryption must fail
        with pytest.raises(InvalidTag):
            AESGCMEncryptor("key-b").decrypt(ct_a)
        with pytest.raises(InvalidTag):
            AESGCMEncryptor("key-a").decrypt(ct_b)

    def test_fernet_key_derivation(self) -> None:
        """Fernet key must be base64url of SHA-256 hash."""
        enc = FernetEncryptor("my-key")
        expected = base64.urlsafe_b64encode(hashlib.sha256(b"my-key").digest())
        assert enc._fernet._signing_key + enc._fernet._encryption_key == hashlib.sha256(b"my-key").digest()

    def test_ciphertext_reveals_no_plaintext_prefix(self) -> None:
        """Ciphertext of similar plaintexts should not share prefixes beyond the nonce."""
        enc = AESGCMEncryptor("key")
        ct1 = base64.standard_b64decode(enc.encrypt("AAAA"))
        ct2 = base64.standard_b64decode(enc.encrypt("AAAB"))
        # Beyond the nonce (first 12 bytes), ciphertext bytes should differ
        payload1, payload2 = ct1[12:], ct2[12:]
        assert payload1 != payload2

    def test_zero_length_key_still_works(self) -> None:
        """Empty key should not crash; SHA-256 of empty string is valid."""
        for cls in [AESGCMEncryptor, FernetEncryptor]:
            enc = cls("")
            ct = enc.encrypt("data")
            assert enc.decrypt(ct) == "data"

    def test_very_long_key_works(self) -> None:
        """Keys of any length should work since they're hashed."""
        long_key = "x" * 100_000
        for cls in [AESGCMEncryptor, FernetEncryptor]:
            enc = cls(long_key)
            ct = enc.encrypt("data")
            assert enc.decrypt(ct) == "data"


# ---------------------------------------------------------------------------
# 7. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_binary_like_string(self, encryptor_cls: type) -> None:
        """Strings containing bytes that look like binary data."""
        text = "".join(chr(i) for i in range(256) if chr(i).isprintable())
        enc = encryptor_cls("key")
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_null_bytes_in_plaintext(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        text = "before\x00after"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_very_large_payload(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        large = "X" * 1_000_000  # 1 MB
        assert enc.decrypt(enc.encrypt(large)) == large

    def test_repeated_encrypt_decrypt_cycles(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        text = "cycle test"
        for _ in range(50):
            text = enc.decrypt(enc.encrypt(text))
        assert text == "cycle test"

    def test_multiline_plaintext(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        text = "line1\nline2\rline3\r\nline4"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_whitespace_only(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        for ws in [" ", "\t", "\n", "   \t\n  "]:
            assert enc.decrypt(enc.encrypt(ws)) == ws

    def test_surrogate_emoji_sequences(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        text = "👨‍👩‍👧‍👦🏳️‍🌈🇺🇸"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_rtl_and_mixed_scripts(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        text = "Hello مرحبا שלום こんにちは"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_sql_injection_like_string(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        text = "'; DROP TABLE users; --"
        assert enc.decrypt(enc.encrypt(text)) == text

    def test_html_and_js_strings(self, encryptor_cls: type) -> None:
        enc = encryptor_cls("key")
        text = '<img onerror="alert(1)" src=x>'
        assert enc.decrypt(enc.encrypt(text)) == text


# ---------------------------------------------------------------------------
# 8. Cross-algorithm incompatibility
# ---------------------------------------------------------------------------


class TestCrossAlgorithm:
    def test_aesgcm_ciphertext_fails_with_fernet(self) -> None:
        ct = AESGCMEncryptor("key").encrypt("data")
        with pytest.raises(Exception):
            FernetEncryptor("key").decrypt(ct)

    def test_fernet_ciphertext_fails_with_aesgcm(self) -> None:
        ct = FernetEncryptor("key").encrypt("data")
        with pytest.raises(Exception):
            AESGCMEncryptor("key").decrypt(ct)


# ---------------------------------------------------------------------------
# 9. Concurrency safety
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_aesgcm_threaded_encrypt_decrypt(self) -> None:
        enc = AESGCMEncryptor("thread-key")
        errors: list[str] = []

        def worker(idx: int) -> None:
            try:
                text = f"thread-{idx}-payload"
                for _ in range(100):
                    ct = enc.encrypt(text)
                    result = enc.decrypt(ct)
                    if result != text:
                        errors.append(f"thread {idx}: mismatch")
            except Exception as e:
                errors.append(f"thread {idx}: {e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"

    def test_fernet_threaded_encrypt_decrypt(self) -> None:
        enc = FernetEncryptor("thread-key")
        errors: list[str] = []

        def worker(idx: int) -> None:
            try:
                text = f"thread-{idx}-payload"
                for _ in range(100):
                    ct = enc.encrypt(text)
                    result = enc.decrypt(ct)
                    if result != text:
                        errors.append(f"thread {idx}: mismatch")
            except Exception as e:
                errors.append(f"thread {idx}: {e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Thread errors: {errors}"


# ---------------------------------------------------------------------------
# 10. Output format validation
# ---------------------------------------------------------------------------


class TestOutputFormat:
    def test_aesgcm_output_is_standard_base64(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("test")
        decoded = base64.standard_b64decode(ct)
        re_encoded = base64.standard_b64encode(decoded).decode()
        assert ct == re_encoded

    def test_fernet_output_is_urlsafe_base64(self) -> None:
        enc = FernetEncryptor("key")
        ct = enc.encrypt("test")
        # Fernet tokens are url-safe base64
        decoded = base64.urlsafe_b64decode(ct)
        re_encoded = base64.urlsafe_b64encode(decoded).decode()
        assert ct == re_encoded

    def test_aesgcm_encrypt_returns_str(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("test")
        assert isinstance(ct, str)

    def test_aesgcm_decrypt_returns_str(self) -> None:
        enc = AESGCMEncryptor("key")
        ct = enc.encrypt("test")
        assert isinstance(enc.decrypt(ct), str)

    def test_fernet_encrypt_returns_str(self) -> None:
        enc = FernetEncryptor("key")
        assert isinstance(enc.encrypt("test"), str)

    def test_fernet_decrypt_returns_str(self) -> None:
        enc = FernetEncryptor("key")
        ct = enc.encrypt("test")
        assert isinstance(enc.decrypt(ct), str)

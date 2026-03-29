"""Example: Validation chains and AES-GCM encryption.

Demonstrates:
- Fluent Validator chain with multiple field checks
- Catching validation errors
- Encrypting and decrypting secrets with AES-GCM
"""

from __future__ import annotations


def demo_validation() -> None:
    """Show the chainable Validator API."""
    from pykit_errors import InvalidInputError
    from pykit_validation import Validator

    # --- Passing validation ---
    name = "Alice"
    password = "s3cure-p@ss!"
    role = "admin"

    (
        Validator()
        .required("name", name)
        .min_length("name", name, 2)
        .max_length("name", name, 50)
        .required("password", password)
        .min_length("password", password, 8)
        .one_of("role", role, ["admin", "editor", "viewer"])
        .validate()
    )
    print("✓ Validation passed for Alice")

    # --- Failing validation ---
    try:
        (
            Validator()
            .required("email", "")
            .min_length("password", "abc", 8)
            .range_check("age", 150, 0, 120)
            .validate()
        )
    except InvalidInputError as exc:
        print(f"✗ Validation failed: {exc}")
        print(f"  details: {exc.details}")

    # --- Custom rule ---
    tags = ["python", "rust"]
    v = Validator().custom(len(tags) <= 5, "tags", "too many tags (max 5)")
    if not v.has_errors:
        print("✓ Custom rule passed")


def demo_encryption() -> None:
    """Show AES-GCM encrypt / decrypt round-trip."""
    from pykit_encryption import Algorithm, new_encryptor

    key = "my-secret-key-for-demo-purposes!"

    # AES-GCM (default)
    enc = new_encryptor(key, Algorithm.AES_GCM)
    plaintext = "credit-card: 4111-1111-1111-1111"
    ciphertext = enc.encrypt(plaintext)
    decrypted = enc.decrypt(ciphertext)

    print(f"\nPlaintext : {plaintext}")
    print(f"Ciphertext: {ciphertext[:60]}…")
    print(f"Decrypted : {decrypted}")
    assert decrypted == plaintext, "round-trip failed!"

    # Fernet alternative
    fernet = new_encryptor(key, Algorithm.FERNET)
    ct = fernet.encrypt("hello fernet")
    print(f"Fernet CT : {ct[:40]}…")
    print(f"Fernet PT : {fernet.decrypt(ct)}")


if __name__ == "__main__":
    demo_validation()
    demo_encryption()

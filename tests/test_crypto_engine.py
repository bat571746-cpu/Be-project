"""
test_crypto_engine.py
======================
Basic sanity tests for the double-encryption pipeline.

Run with:
    python -m pytest tests/ -v
or simply:
    python tests/test_crypto_engine.py
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.crypto_engine import CryptoEngine
from core.qrng import QuantumRandomGenerator
from cryptography.exceptions import InvalidTag


def test_text_roundtrip():
    engine = CryptoEngine()
    original = "Quantum-assisted encryption is the future of secure communication."
    password = "correct-horse-battery-staple"

    blob = engine.encrypt_text(original, password)
    recovered = engine.decrypt_text(blob, password)

    assert recovered == original, "Decrypted text does not match original!"
    print("[PASS] test_text_roundtrip")


def test_wrong_password_fails():
    engine = CryptoEngine()
    blob = engine.encrypt_text("secret message", "right-password")

    try:
        engine.decrypt_text(blob, "wrong-password")
        raise AssertionError("Decryption should have failed with wrong password!")
    except InvalidTag:
        print("[PASS] test_wrong_password_fails")


def test_file_roundtrip():
    engine = CryptoEngine()
    password = "file-test-password-123"

    with tempfile.TemporaryDirectory() as tmpdir:
        original_path = os.path.join(tmpdir, "original.txt")
        encrypted_path = os.path.join(tmpdir, "original.txt.qaes")
        decrypted_path = os.path.join(tmpdir, "decrypted.txt")

        original_content = b"This is binary-safe test content.\x00\x01\xff"
        with open(original_path, "wb") as f:
            f.write(original_content)

        engine.encrypt_file(original_path, encrypted_path, password)
        engine.decrypt_file(encrypted_path, decrypted_path, password)

        with open(decrypted_path, "rb") as f:
            decrypted_content = f.read()

        assert decrypted_content == original_content, "File round-trip failed!"
        print("[PASS] test_file_roundtrip")


def test_tampered_ciphertext_detected():
    engine = CryptoEngine()
    blob = bytearray(engine.encrypt_text("integrity check", "some-password"))
    blob[-1] ^= 0xFF  # flip bits in the last byte (inside the GCM tag/ciphertext)

    try:
        engine.decrypt_text(bytes(blob), "some-password")
        raise AssertionError("Tampered ciphertext should have failed integrity check!")
    except InvalidTag:
        print("[PASS] test_tampered_ciphertext_detected")


def test_qrng_produces_varying_output():
    qrng = QuantumRandomGenerator()
    sample1 = qrng.get_random_bytes(8)
    sample2 = qrng.get_random_bytes(8)
    assert sample1 != sample2, "QRNG produced identical samples (unlikely if working correctly)!"
    print(f"[PASS] test_qrng_produces_varying_output  (sample1={sample1.hex()}, sample2={sample2.hex()})")


if __name__ == "__main__":
    test_text_roundtrip()
    test_wrong_password_fails()
    test_file_roundtrip()
    test_tampered_ciphertext_detected()
    test_qrng_produces_varying_output()
    print("\nAll tests passed.")

"""
aes_cipher.py
=============
Classical encryption layer: AES-256 in GCM mode (Galois/Counter Mode).

This is the "trusted, standard" half of the double-encryption scheme.
AES-GCM is an Authenticated Encryption with Associated Data (AEAD) cipher:
it does not just encrypt data, it also produces a 16-byte authentication
TAG. On decryption, if even a single bit of the ciphertext was changed
(corruption, tampering, wrong key), verification fails and decryption
raises an exception instead of silently returning garbage. This is a key
advantage over plain AES-CBC, which has no built-in tamper detection.

We use the `cryptography` library's AESGCM implementation (audited,
well-tested, hardware-accelerated) rather than hand-rolling AES, since
hand-rolled AES is both extremely error-prone and provides no real
security if implemented imperfectly. The "from scratch" / novel part of
this project lives in the quantum random number generator (qrng.py),
not in re-implementing AES.

Key sizes:
    AES-256 key  -> 32 bytes
    GCM nonce/IV -> 12 bytes (96 bits, the recommended size for GCM)
    GCM tag      -> 16 bytes (appended automatically by the library)
"""

from __future__ import annotations

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

AES_KEY_SIZE = 32     # AES-256
GCM_NONCE_SIZE = 12   # 96-bit nonce, recommended for GCM


class AESCipher:
    """
    Wraps AES-256-GCM encryption/decryption.

    The key and nonce are NOT generated here -- they are supplied by the
    caller (crypto_engine.py), which sources them from the quantum random
    number generator. This keeps responsibilities cleanly separated:
        qrng.py          -> produces randomness
        aes_cipher.py     -> performs the actual symmetric encryption
        crypto_engine.py  -> wires the two together
    """

    def __init__(self, key: bytes):
        if len(key) != AES_KEY_SIZE:
            raise ValueError(
                f"AES-256 requires a {AES_KEY_SIZE}-byte key, got {len(key)} bytes"
            )
        self._aesgcm = AESGCM(key)

    def encrypt(self, plaintext: bytes, nonce: bytes, associated_data: bytes = None) -> bytes:
        """
        Encrypts plaintext bytes with AES-256-GCM.
        Returns ciphertext with the 16-byte auth tag appended (this is
        the standard behaviour of the `cryptography` AESGCM class).
        """
        if len(nonce) != GCM_NONCE_SIZE:
            raise ValueError(f"GCM nonce must be {GCM_NONCE_SIZE} bytes, got {len(nonce)}")
        return self._aesgcm.encrypt(nonce, plaintext, associated_data)

    def decrypt(self, ciphertext: bytes, nonce: bytes, associated_data: bytes = None) -> bytes:
        """
        Decrypts ciphertext (with appended tag) using AES-256-GCM.
        Raises `cryptography.exceptions.InvalidTag` if the tag does not
        match -- i.e. wrong key, wrong nonce, or the data was tampered with.
        """
        if len(nonce) != GCM_NONCE_SIZE:
            raise ValueError(f"GCM nonce must be {GCM_NONCE_SIZE} bytes, got {len(nonce)}")
        return self._aesgcm.decrypt(nonce, ciphertext, associated_data)

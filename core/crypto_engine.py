"""
crypto_engine.py
=================
Orchestrates the full double-encryption pipeline:

    1. QUANTUM LAYER  (qrng.py)
       A quantum circuit generates a random "quantum seed" -- genuine
       quantum entropy, not a classical PRNG.

    2. HYBRID KEY DERIVATION
       The user's password AND the quantum seed are combined through a
       Key Derivation Function (KDF) -- specifically PBKDF2-HMAC-SHA256 --
       to produce the actual AES-256 key. This means:
           - An attacker who only guesses the password cannot derive the
             key without also knowing the quantum seed (which is randomly
             generated per-encryption and stored alongside the ciphertext,
             analogous to a salt).
           - An attacker who somehow obtained the quantum seed still
             cannot derive the key without the password.
       This is why the scheme is called "double encryption" / hybrid:
       security depends on BOTH a classical secret (password) and a
       quantum-generated secret (seed), combined via the KDF, then used
       to drive AES-256-GCM (aes_cipher.py).

    3. CLASSICAL LAYER  (aes_cipher.py)
       AES-256-GCM performs the actual confidentiality + integrity
       protection of the plaintext, using the derived key and a
       quantum-generated nonce.

Output container format (all binary, written to a single .qaes file or
returned as bytes for text mode):

    MAGIC (4 bytes)  | VERSION (1 byte) | salt (16B) | quantum_seed (16B)
    | kdf_iterations (4B, big-endian) | nonce (12B) | ciphertext+tag (rest)

Storing the quantum_seed and salt alongside the ciphertext is standard
practice (same principle as storing a salt next to a password hash) --
they are not secret on their own, they only become useful in combination
with the password.
"""

from __future__ import annotations

import struct
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.qrng import QuantumRandomGenerator
from core.aes_cipher import AESCipher, AES_KEY_SIZE, GCM_NONCE_SIZE

MAGIC = b"QAES"          # identifies our file format
VERSION = 1
SALT_SIZE = 16
QUANTUM_SEED_SIZE = 16
KDF_ITERATIONS = 390_000  # OWASP-recommended minimum for PBKDF2-HMAC-SHA256 (2023+)

HEADER_STRUCT = ">4sB16s16sI12s"  # magic, version, salt, qseed, iterations, nonce
HEADER_SIZE = struct.calcsize(HEADER_STRUCT)


class CryptoEngine:
    """
    High-level API used by the GUI. Handles both text and file encryption
    using the quantum-assisted hybrid scheme described above.
    """

    def __init__(self):
        self._qrng = QuantumRandomGenerator()

    # ------------------------------------------------------------------
    # Key derivation
    # ------------------------------------------------------------------
    def _derive_key(self, password: str, salt: bytes, quantum_seed: bytes,
                     iterations: int) -> bytes:
        """
        Combines the password and the quantum seed into the KDF input,
        then stretches it into a 256-bit AES key via PBKDF2-HMAC-SHA256.
        """
        password_bytes = password.encode("utf-8")
        # Concatenating password + quantum_seed means the derived key
        # depends on BOTH secrets -- the "double" in double encryption.
        kdf_input = password_bytes + quantum_seed

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=AES_KEY_SIZE,
            salt=salt,
            iterations=iterations,
        )
        return kdf.derive(kdf_input)

    # ------------------------------------------------------------------
    # Encryption
    # ------------------------------------------------------------------
    def encrypt_bytes(self, plaintext: bytes, password: str) -> bytes:
        """
        Encrypts arbitrary bytes (file contents or UTF-8 text) and returns
        a self-contained binary blob: header + ciphertext.
        """
        salt = os.urandom(SALT_SIZE)                      # classical salt
        quantum_seed = self._qrng.get_random_bytes(QUANTUM_SEED_SIZE)  # quantum entropy
        nonce = self._qrng.get_random_bytes(GCM_NONCE_SIZE)            # quantum nonce

        key = self._derive_key(password, salt, quantum_seed, KDF_ITERATIONS)
        cipher = AESCipher(key)
        ciphertext = cipher.encrypt(plaintext, nonce)

        header = struct.pack(
            HEADER_STRUCT,
            MAGIC, VERSION, salt, quantum_seed, KDF_ITERATIONS, nonce
        )
        return header + ciphertext

    def encrypt_text(self, plaintext: str, password: str) -> bytes:
        return self.encrypt_bytes(plaintext.encode("utf-8"), password)

    def encrypt_file(self, input_path: str, output_path: str, password: str) -> None:
        with open(input_path, "rb") as f:
            data = f.read()
        blob = self.encrypt_bytes(data, password)
        with open(output_path, "wb") as f:
            f.write(blob)

    # ------------------------------------------------------------------
    # Decryption
    # ------------------------------------------------------------------
    def decrypt_bytes(self, blob: bytes, password: str) -> bytes:
        """
        Reverses encrypt_bytes(). Raises ValueError on a malformed/foreign
        file, and cryptography.exceptions.InvalidTag on wrong password or
        tampered/corrupted ciphertext.
        """
        if len(blob) < HEADER_SIZE:
            raise ValueError("File too small to be a valid QAES container.")

        header = blob[:HEADER_SIZE]
        ciphertext = blob[HEADER_SIZE:]

        magic, version, salt, quantum_seed, iterations, nonce = struct.unpack(
            HEADER_STRUCT, header
        )

        if magic != MAGIC:
            raise ValueError("Not a valid QAES-encrypted file (bad magic header).")
        if version != VERSION:
            raise ValueError(f"Unsupported QAES format version: {version}")

        key = self._derive_key(password, salt, quantum_seed, iterations)
        cipher = AESCipher(key)
        return cipher.decrypt(ciphertext, nonce)  # raises InvalidTag if wrong

    def decrypt_text(self, blob: bytes, password: str) -> str:
        return self.decrypt_bytes(blob, password).decode("utf-8")

    def decrypt_file(self, input_path: str, output_path: str, password: str) -> None:
        with open(input_path, "rb") as f:
            blob = f.read()
        plaintext = self.decrypt_bytes(blob, password)
        with open(output_path, "wb") as f:
            f.write(plaintext)

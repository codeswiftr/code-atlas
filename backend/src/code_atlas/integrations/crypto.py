"""Symmetric token encryption using the Python standard library only.

We use an XOR keystream derived from PBKDF2-HMAC-SHA256 so that we never
persist raw OAuth tokens.  The scheme is:

    ciphertext = plaintext XOR PRNG-stream(key, nonce)

where the PRNG stream is produced by iterating SHA-256 blocks:

    block_i = HMAC-SHA256(key=derived_key, msg=nonce || i.to_bytes(4))

This gives 256-bit security equivalent to AES-CTR when the server key is kept
secret.  It is deliberately simple: no dependencies beyond ``hashlib``,
``hmac``, ``os``, and ``base64``.

Environment variable: ``CODE_ATLAS_TOKEN_SECRET`` (32+ bytes of randomness).
A per-process fallback is generated when the env var is absent so that tests
pass without configuration; tokens encrypted in that ephemeral key cannot be
decrypted across restarts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import struct

# ---------------------------------------------------------------------------
# Server-side encryption key
# ---------------------------------------------------------------------------

_SECRET_ENV = "CODE_ATLAS_TOKEN_SECRET"
_EPHEMERAL_KEY: bytes | None = None


def _get_server_key() -> bytes:
    """Return the server-side encryption key as raw bytes.

    Reads ``CODE_ATLAS_TOKEN_SECRET`` from the environment.  Falls back to a
    stable per-process ephemeral key for local development and tests.
    """
    global _EPHEMERAL_KEY  # noqa: PLW0603

    env_val = os.environ.get(_SECRET_ENV, "")
    if env_val:
        raw = env_val.encode()
        # Stretch to 32 bytes via SHA-256 so arbitrary-length secrets work
        return hashlib.sha256(raw).digest()

    # Generate once per process so encrypt/decrypt round-trips work in tests
    if _EPHEMERAL_KEY is None:
        _EPHEMERAL_KEY = os.urandom(32)
    return _EPHEMERAL_KEY


# ---------------------------------------------------------------------------
# Core keystream helper
# ---------------------------------------------------------------------------

def _keystream(derived_key: bytes, nonce: bytes, length: int) -> bytes:
    """Generate *length* bytes of keystream using HMAC-SHA256 in counter mode."""
    stream = bytearray()
    block_index = 0
    while len(stream) < length:
        block = hmac.new(
            derived_key,
            nonce + struct.pack(">I", block_index),
            hashlib.sha256,
        ).digest()
        stream.extend(block)
        block_index += 1
    return bytes(stream[:length])


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_NONCE_LEN = 16  # 128-bit random nonce per encryption


def encrypt_token(plaintext: str) -> str:
    """Encrypt *plaintext* and return a URL-safe base64-encoded ciphertext.

    Format: ``base64(nonce || ciphertext)`` where both parts are raw bytes.
    """
    server_key = _get_server_key()
    nonce = os.urandom(_NONCE_LEN)

    # Derive a per-nonce key so the same server key + different nonces produce
    # independent keystreams.
    derived = hashlib.pbkdf2_hmac("sha256", server_key, nonce, iterations=1, dklen=32)

    raw = plaintext.encode("utf-8")
    ks = _keystream(derived, nonce, len(raw))
    cipher = bytes(a ^ b for a, b in zip(raw, ks, strict=True))

    payload = nonce + cipher
    return base64.urlsafe_b64encode(payload).decode("ascii")


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a ciphertext produced by :func:`encrypt_token`.

    Raises:
        ValueError: If the payload is malformed or too short.
    """
    try:
        payload = base64.urlsafe_b64decode(ciphertext.encode("ascii"))
    except Exception as exc:
        raise ValueError("Malformed ciphertext: base64 decode failed") from exc

    if len(payload) < _NONCE_LEN:
        raise ValueError(
            f"Ciphertext too short: expected at least {_NONCE_LEN} bytes, "
            f"got {len(payload)}"
        )

    server_key = _get_server_key()
    nonce = payload[:_NONCE_LEN]
    cipher = payload[_NONCE_LEN:]

    derived = hashlib.pbkdf2_hmac("sha256", server_key, nonce, iterations=1, dklen=32)
    ks = _keystream(derived, nonce, len(cipher))
    raw = bytes(a ^ b for a, b in zip(cipher, ks, strict=True))

    return raw.decode("utf-8")

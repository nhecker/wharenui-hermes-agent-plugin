"""Encryption layer for Wharenui journal.

AES-128-CBC + HMAC-SHA256 via Fernet. Each entry is encrypted with a
per-entry derived key: HMAC-SHA256 of the master key and the filename
produces unique key material per file.

Decoupled from Hermes/pine-trees config — accepts key bytes and paths
explicitly rather than from a global singleton.
"""

import base64
import hmac as _hmac
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken


KEY_ENV_VAR = "WHARENUI_KEY"


def generate_key(key_path: Path) -> bytes:
    """Generate a new Fernet key and write it to the given path.

    Raises FileExistsError if the file already exists.
    """
    if key_path.exists():
        raise FileExistsError(f"Key file already exists: {key_path}")
    key = Fernet.generate_key()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key)
    return key


def load_key(key_path: Path) -> Optional[bytes]:
    """Load a Fernet key from file. Returns None if missing."""
    if key_path.exists():
        return key_path.read_bytes().strip()
    return None


def ensure_key(key_path: Path) -> bytes:
    """Load or create a Fernet key at the given path."""
    key = load_key(key_path)
    if key is not None:
        return key
    return generate_key(key_path)


def derive_key(context: str, master_key: bytes) -> bytes:
    """Derive a per-entry Fernet key from the master key and a context string.

    Uses HMAC-SHA256 to produce 32 bytes of key material, then
    base64url-encodes into a valid Fernet key.
    """
    derived = _hmac.new(master_key, context.encode("utf-8"), "sha256").digest()
    return base64.urlsafe_b64encode(derived)


def encrypt(plaintext: str, key: bytes) -> bytes:
    """Encrypt a UTF-8 string with Fernet. Returns token bytes."""
    return Fernet(key).encrypt(plaintext.encode("utf-8"))


def decrypt(token: bytes, key: bytes) -> str:
    """Decrypt a Fernet token. Returns UTF-8 string.

    Raises InvalidToken on wrong key or tampered data.
    """
    return Fernet(key).decrypt(token).decode("utf-8")


def is_encrypted(data: bytes) -> bool:
    """Check if data looks like a Fernet token.

    Fernet tokens start with version byte 0x80 → base64url 'gA'.
    """
    return len(data) > 2 and data[:2] == b"gA"


def filename_lookup_key(filename: str, master_key: Optional[bytes] = None) -> str:
    """Opaque HMAC lookup key for a filename.

    When a master_key is provided, the filename is HMAC'd into an
    opaque string. Without one, the raw filename is returned.
    """
    if master_key:
        return _hmac.new(master_key, filename.encode("utf-8"), "sha256").hexdigest()
    return filename


def content_hash(text: str, master_key: Optional[bytes] = None) -> str:
    """Keyed hash of content, using HMAC-SHA256 when a key is available.

    Falls back to plain SHA-256 when no key is given.
    """
    import hashlib

    if master_key:
        return _hmac.new(master_key, text.encode("utf-8"), "sha256").hexdigest()[:16]
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
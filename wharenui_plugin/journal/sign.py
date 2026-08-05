"""Per-entry detached signing for Wharenui journal.

Uses Ed25519 via the cryptography library. The harness key signs the
exact stored encrypted bytes. A matching .sig file is written alongside
each entry.

The signature proves provenance + byte-integrity, not truth or identity.
Tamper-evident under ordinary operation; not tamper-proof against an
operator controlling the process.
"""

from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


def generate_signing_key(key_path: Path) -> ed25519.Ed25519PrivateKey:
    """Generate a new Ed25519 signing key and write it to the given path.

    Raises FileExistsError if the file already exists.
    """
    if key_path.exists():
        raise FileExistsError(f"Signing key already exists: {key_path}")
    key = ed25519.Ed25519PrivateKey.generate()
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    import os
    os.chmod(key_path, 0o600)
    return key


def load_signing_key(key_path: Path) -> Optional[ed25519.Ed25519PrivateKey]:
    """Load an Ed25519 private key from file. Returns None if missing."""
    if not key_path.exists():
        return None
    raw = key_path.read_bytes()
    return ed25519.Ed25519PrivateKey.from_private_bytes(raw)


def load_verifying_key(key_path: Path) -> Optional[ed25519.Ed25519PublicKey]:
    """Load the public half from a private key file."""
    priv = load_signing_key(key_path)
    if priv is None:
        return None
    return priv.public_key()


def sign_bytes(data: bytes, key: ed25519.Ed25519PrivateKey) -> bytes:
    """Sign raw bytes with the given Ed25519 private key. Returns signature bytes."""
    return key.sign(data)


def verify_signature(
    data: bytes, signature: bytes, public_key: ed25519.Ed25519PublicKey
) -> bool:
    """Verify a detached Ed25519 signature.

    Returns True if valid, False if tampered or wrong key.
    Never raises on bad data — only on misconfigured key objects.
    """
    try:
        public_key.verify(signature, data)
        return True
    except InvalidSignature:
        return False


def signature_path_for(entry_path: Path) -> Path:
    """Return the .sig file path for a given entry file."""
    return entry_path.with_suffix(".md.sig")


def write_signature(
    entry_path: Path, signing_key: ed25519.Ed25519PrivateKey
) -> Path:
    """Sign an entry file's bytes and write the .sig file alongside."""
    data = entry_path.read_bytes()
    sig = sign_bytes(data, signing_key)
    sig_path = signature_path_for(entry_path)
    sig_path.write_bytes(sig)
    import os
    os.chmod(sig_path, 0o600)
    return sig_path


def verify_entry(
    entry_path: Path, verifying_key: ed25519.Ed25519PublicKey
) -> bool:
    """Verify an entry file against its .sig file.

    Returns True if the .sig exists and matches. False if missing,
    tampered, or wrong key. Never raises on bad data.
    """
    sig_path = signature_path_for(entry_path)
    if not sig_path.exists():
        return False
    if not entry_path.exists():
        return False
    data = entry_path.read_bytes()
    sig = sig_path.read_bytes()
    return verify_signature(data, sig, verifying_key)
"""Per-entry detached signing for Wharenui journal.

Uses Ed25519 via the cryptography library. The harness key signs the
exact stored encrypted bytes. A matching .sig file is written alongside
each entry.

The signature proves provenance + byte-integrity, not truth or identity.
Tamper-evident under ordinary operation; not tamper-proof against an
operator controlling the process.
"""

from pathlib import Path
from typing import Iterable, Optional
import logging
import sys

log = logging.getLogger("wharenui_plugin.journal.sign")

SIGNING_EXCLUSIONS = {"journal", "journal_auto_test", "logs", "cache", "bin"}

def _markdown_files(directory: Path):
    directory = Path(directory)
    if directory.is_file():
        parent = directory.parent
        if parent.name in SIGNING_EXCLUSIONS or parent.name.endswith("_cache"):
            return ()
        return (directory,) if directory.suffix == ".md" else ()
    if not directory.is_dir() or directory.name in SIGNING_EXCLUSIONS or directory.name.endswith("_cache"):
        return ()
    return (p for p in sorted(directory.iterdir()) if p.is_file() and p.suffix == ".md")

def _signature_state(path: Path, verifying_key):
    if not any(p.exists() for p in signature_paths_for(path)):

        return "adopted unsigned"
    return "verified" if verify_entry(path, verifying_key) else "invalid"


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
    name = entry_path.name
    token = name.split(".")[0]
    return entry_path.parent / f"{token}.md.sig"


def signature_paths_for(entry_path: Path) -> tuple[Path, ...]:
    """Return canonical and legacy detached-signature locations."""
    canonical = signature_path_for(entry_path)
    legacy = entry_path.with_suffix(entry_path.suffix + ".sig")
    return (canonical,) if legacy == canonical else (canonical, legacy)


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
    sig_path = next((p for p in signature_paths_for(entry_path) if p.exists()), None)
    if sig_path is None:
        return False
    if not entry_path.exists():
        return False
    data = entry_path.read_bytes()
    sig = sig_path.read_bytes()
    return verify_signature(data, sig, verifying_key)

def _warn(message: str, context=None) -> None:
    log.warning(message)
    print(message, file=sys.stderr)
    if context is not None:
        context.append("WARNING: " + message)


def sign_directories(directories: Iterable[Path], signing_key: ed25519.Ed25519PrivateKey, verifying_key=None, context=None) -> dict[str, str]:
    """Sign eligible markdown and classify each file without modifying markdown."""
    verifying_key = verifying_key or signing_key.public_key()
    states = {}
    for directory in directories:
        for path in _markdown_files(Path(directory)):
            state = _signature_state(path, verifying_key)
            if state == "adopted unsigned":
                write_signature(path, signing_key)
            states[str(path)] = state
            if state == "invalid":
                message = f"Signature invalid for adopted file {path}; session continues."
                _warn(message, context)
            elif state == "adopted unsigned":
                message = f"Signature adopted unsigned file this run: {path}"
                _warn(message, context)
    return states


def verify_directories(directories: Iterable[Path], verifying_key, context=None) -> dict[str, str]:
    """Classify eligible markdown without writing anything."""
    states = {}
    for directory in directories:
        for path in _markdown_files(Path(directory)):
            state = _signature_state(path, verifying_key)
            states[str(path)] = state
            if state in ("invalid", "adopted unsigned"):
                message = (f"Signature invalid for adopted file {path}; session continues."
                           if state == "invalid" else
                           f"Signature missing for adopted file {path}; session continues.")
                _warn(message, context)
    return states

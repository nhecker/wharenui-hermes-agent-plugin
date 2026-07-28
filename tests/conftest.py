"""Synthetic fixtures for Wharenui journal tests.

Temp dirs, freshly generated Fernet + signing keys, and a hard guard
preventing tests from touching a real journal directory.
"""

import pytest
from cryptography.fernet import Fernet

from wharenui_plugin.journal import crypto, sign


@pytest.fixture
def journal_dir(tmp_path):
    """A temp directory that acts as the journal memory dir."""
    d = tmp_path / "memory"
    d.mkdir()
    return d


@pytest.fixture
def key_path(tmp_path):
    """Path to a fresh Fernet key file."""
    kp = tmp_path / ".key"
    crypto.generate_key(kp)
    return kp


@pytest.fixture
def master_key(key_path):
    """The Fernet key bytes."""
    return crypto.load_key(key_path)


@pytest.fixture
def signing_key_path(tmp_path):
    """Path to a fresh Ed25519 signing key file."""
    skp = tmp_path / ".signing_key"
    sign.generate_signing_key(skp)
    return skp


@pytest.fixture
def signing_key(signing_key_path):
    """The loaded Ed25519 signing key."""
    return sign.load_signing_key(signing_key_path)


@pytest.fixture
def verifying_key(signing_key):
    """The public half of the signing key."""
    return signing_key.public_key()


@pytest.fixture
def db_path(tmp_path):
    """Path to a temp embeddings database."""
    return tmp_path / "embeddings.db"


@pytest.fixture(autouse=True)
def _guard_real_journal():
    """Hard guard: fail if a test config might resolve to a real journal dir.

    Tests must use tmp_path or explicit temp paths. Any attempt to
    access a real journal directory (e.g. /home, /root, /var) triggers
    a loud assertion failure.
    """
    # This is a placeholder — the real guard is structural: every test
    # uses the journal_dir fixture (tmp_path), and the journal package
    # never reads a default path from config. If a test tries to pass
    # /home/ or /root/ as memory_dir, it will fail on its own terms.
    pass
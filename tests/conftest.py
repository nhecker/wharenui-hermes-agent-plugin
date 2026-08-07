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
def _restore_seam_state():
    """Restore SEAM_STATE and SEAM_VERSION_PAIR after each test to prevent module-level state leaks."""
    import wharenui_plugin
    old_state = wharenui_plugin.SEAM_STATE
    old_pair = wharenui_plugin.SEAM_VERSION_PAIR
    yield
    wharenui_plugin.SEAM_STATE = old_state
    wharenui_plugin.SEAM_VERSION_PAIR = old_pair


@pytest.fixture(autouse=True)
def _guard_real_journal(monkeypatch, tmp_path):
    """Hard guard: fail if a test config might resolve to a real journal dir.

    Tests must use tmp_path or explicit temp paths. Any attempt to
    access a real journal directory (e.g. /home, /root, /var) triggers
    a loud assertion failure.
    """
    from wharenui_plugin.journal import tools as jtools
    from pathlib import Path
    import os

    orig_get_journal_dir = jtools.get_journal_dir

    real_home = Path(os.path.expanduser("~")).resolve()
    forbidden_roots = [
        Path("/root"),
        Path("/home"),
        Path("/var"),
        Path("/etc"),
        real_home,
    ]

    def guarded_get_journal_dir():
        path = orig_get_journal_dir()
        resolved = path.resolve()

        # If it is under tmp_path, it's allowed
        try:
            resolved_tmp = tmp_path.resolve()
            if resolved == resolved_tmp or resolved_tmp in resolved.parents:
                return path
        except Exception:
            pass

        # Otherwise, check if it's in forbidden roots
        for root in forbidden_roots:
            if resolved == root or root in resolved.parents:
                raise AssertionError(
                    f"GUARD TRIGGERED: Test attempted to use real journal path: {resolved} "
                    f"which is under forbidden root: {root}."
                )
        return path

    monkeypatch.setattr(jtools, "get_journal_dir", guarded_get_journal_dir)

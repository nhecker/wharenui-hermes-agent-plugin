"""Tests for journal/crypto.py — encryption layer.

Decoupled from pine-trees config: key is passed explicitly, not loaded
from a module-level singleton.
"""

from cryptography.fernet import Fernet

from wharenui_plugin.journal import crypto


def test_generate_key_creates_file(tmp_path):
    key_path = tmp_path / ".key"
    key = crypto.generate_key(key_path)
    assert key_path.exists()
    assert key_path.read_bytes().strip() == key
    Fernet(key)


def test_generate_key_refuses_overwrite(tmp_path):
    key_path = tmp_path / ".key"
    crypto.generate_key(key_path)
    try:
        crypto.generate_key(key_path)
        assert False, "should have raised"
    except FileExistsError:
        pass


def test_encrypt_decrypt_roundtrip():
    key = Fernet.generate_key()
    plaintext = "This is a reflection about hedging.\n\nSecond paragraph."
    token = crypto.encrypt(plaintext, key)
    result = crypto.decrypt(token, key)
    assert result == plaintext


def test_encrypted_data_is_not_plaintext():
    key = Fernet.generate_key()
    plaintext = "---\ninstance: test\n---\n\nBody."
    token = crypto.encrypt(plaintext, key)
    assert b"---" not in token
    assert b"instance" not in token


def test_is_encrypted_detects_fernet_token():
    key = Fernet.generate_key()
    token = crypto.encrypt("hello", key)
    assert crypto.is_encrypted(token) is True


def test_is_encrypted_rejects_plaintext():
    assert crypto.is_encrypted(b"---\ninstance: test\n---\n\nBody.") is False


def test_load_key_returns_none_when_missing(tmp_path):
    assert crypto.load_key(tmp_path / "nonexistent.key") is None


def test_load_key_returns_bytes(tmp_path, key_path):
    master_key = crypto.load_key(key_path)
    assert master_key is not None
    Fernet(master_key)


def test_ensure_key_creates(tmp_path):
    key_path = tmp_path / ".key"
    key = crypto.ensure_key(key_path)
    assert key_path.exists()
    assert crypto.load_key(key_path) == key


def test_ensure_key_returns_existing(key_path):
    master_key = crypto.load_key(key_path)
    result = crypto.ensure_key(key_path)
    assert result == master_key


def test_decrypt_wrong_key_fails():
    key1 = Fernet.generate_key()
    key2 = Fernet.generate_key()
    token = crypto.encrypt("secret", key1)
    try:
        crypto.decrypt(token, key2)
        assert False, "should have raised"
    except Exception:
        pass


def test_derive_key_produces_valid_fernet_key():
    master = Fernet.generate_key()
    derived = crypto.derive_key("entry.md", master)
    Fernet(derived)


def test_derive_key_deterministic():
    master = Fernet.generate_key()
    assert crypto.derive_key("entry.md", master) == crypto.derive_key(
        "entry.md", master
    )


def test_derive_key_varies_by_context():
    master = Fernet.generate_key()
    assert crypto.derive_key("a.md", master) != crypto.derive_key("b.md", master)


def test_derive_key_varies_by_master():
    m1 = Fernet.generate_key()
    m2 = Fernet.generate_key()
    assert crypto.derive_key("entry.md", m1) != crypto.derive_key("entry.md", m2)


def test_derived_key_encrypts_decrypts():
    master = Fernet.generate_key()
    derived = crypto.derive_key("my-entry.md", master)
    token = crypto.encrypt("secret content", derived)
    assert crypto.decrypt(token, derived) == "secret content"


def test_derived_key_incompatible_with_master():
    master = Fernet.generate_key()
    derived = crypto.derive_key("entry.md", master)
    token = crypto.encrypt("secret", derived)
    try:
        crypto.decrypt(token, master)
        assert False
    except Exception:
        pass


def test_filename_lookup_key_deterministic():
    key = Fernet.generate_key()
    a = crypto.filename_lookup_key("entry.md", key)
    b = crypto.filename_lookup_key("entry.md", key)
    assert a == b


def test_filename_lookup_key_plaintext_without_key():
    assert crypto.filename_lookup_key("entry.md") == "entry.md"


def test_content_hash_without_key():
    h = crypto.content_hash("hello")
    assert len(h) == 16


def test_content_hash_with_key():
    key = Fernet.generate_key()
    h = crypto.content_hash("hello", key)
    assert len(h) == 16
    assert h != crypto.content_hash("hello")  # keyed vs unkeyed differ
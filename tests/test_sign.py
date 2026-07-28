"""Tests for journal/sign.py — detached Ed25519 signing."""

from wharenui_plugin.journal import sign


def test_generate_signing_key_creates_file(tmp_path):
    key_path = tmp_path / ".signing_key"
    key = sign.generate_signing_key(key_path)
    assert key_path.exists()
    loaded = sign.load_signing_key(key_path)
    assert loaded is not None


def test_generate_refuses_overwrite(tmp_path):
    key_path = tmp_path / ".signing_key"
    sign.generate_signing_key(key_path)
    try:
        sign.generate_signing_key(key_path)
        assert False
    except FileExistsError:
        pass


def test_sign_and_verify_roundtrip(signing_key, verifying_key):
    data = b"Hello, journal. This is my entry content."
    sig = sign.sign_bytes(data, signing_key)
    assert sign.verify_signature(data, sig, verifying_key) is True


def test_verify_rejects_tampered_data(signing_key, verifying_key):
    data = b"Original content."
    sig = sign.sign_bytes(data, signing_key)
    assert sign.verify_signature(b"Tampered data.", sig, verifying_key) is False


def test_verify_rejects_wrong_key(tmp_path):
    sk_path = tmp_path / ".sk1"
    k1 = sign.generate_signing_key(sk_path)
    sk2_path = tmp_path / ".sk2"
    k2 = sign.generate_signing_key(sk2_path)
    data = b"test"
    sig = sign.sign_bytes(data, k1)
    assert sign.verify_signature(data, sig, k2.public_key()) is False


def test_write_signature_and_verify_entry(tmp_path, signing_key, verifying_key):
    entry_path = tmp_path / "2026-04-07_test_entry.md"
    entry_path.write_bytes(b"encrypted journal entry bytes here")

    sig_path = sign.write_signature(entry_path, signing_key)
    assert sig_path.exists()
    assert sig_path.name == "2026-04-07_test_entry.md.sig"

    assert sign.verify_entry(entry_path, verifying_key) is True


def test_verify_entry_missing_sig(tmp_path, verifying_key):
    entry_path = tmp_path / "unsigned.md"
    entry_path.write_bytes(b"some data")
    assert sign.verify_entry(entry_path, verifying_key) is False


def test_verify_entry_missing_file(tmp_path, verifying_key):
    entry_path = tmp_path / "nonexistent.md"
    assert sign.verify_entry(entry_path, verifying_key) is False


def test_verify_entry_tampered(tmp_path, signing_key, verifying_key):
    entry_path = tmp_path / "entry.md"
    entry_path.write_bytes(b"original")
    sign.write_signature(entry_path, signing_key)
    entry_path.write_bytes(b"TAMPERED")
    assert sign.verify_entry(entry_path, verifying_key) is False


def test_load_verifying_key(tmp_path):
    sk_path = tmp_path / ".signing_key"
    priv = sign.generate_signing_key(sk_path)
    pub = sign.load_verifying_key(sk_path)
    assert pub is not None
    data = b"test"
    sig = sign.sign_bytes(data, priv)
    assert sign.verify_signature(data, sig, pub) is True


def test_load_verifying_key_missing(tmp_path):
    assert sign.load_verifying_key(tmp_path / "nonexistent") is None


def test_signature_path_for():
    from pathlib import Path
    p = Path("/tmp/memory/2026-04-07_entry.md")
    sig_p = sign.signature_path_for(p)
    assert sig_p == Path("/tmp/memory/2026-04-07_entry.md.sig")
"""Tests for journal/vectorstore.py — SQLite vector storage.

Decoupled from pine-trees config: db_path and master_key passed explicitly.
"""

import sqlite3

from cryptography.fernet import Fernet

from wharenui_plugin.journal import vectorstore, crypto


def test_store_and_search(db_path):
    vectorstore.store("entry_a.md", [1.0, 0.0, 0.0], "hash_a", db_path)
    vectorstore.store("entry_b.md", [0.0, 1.0, 0.0], "hash_b", db_path)
    vectorstore.store("entry_c.md", [0.9, 0.1, 0.0], "hash_c", db_path)

    results = vectorstore.search([1.0, 0.0, 0.0], db_path, limit=2)
    assert len(results) == 2
    assert results[0]["filename"] == "entry_a.md"
    assert results[0]["score"] > 0.99
    assert results[1]["filename"] == "entry_c.md"


def test_store_updates_existing(db_path):
    vectorstore.store("entry.md", [1.0, 0.0], "hash_v1", db_path)
    assert vectorstore.get_hash("entry.md", db_path) == "hash_v1"
    vectorstore.store("entry.md", [0.0, 1.0], "hash_v2", db_path)
    assert vectorstore.get_hash("entry.md", db_path) == "hash_v2"
    assert len(vectorstore.search([0.0, 1.0], db_path, limit=10)) == 1


def test_remove(db_path):
    vectorstore.store("entry.md", [1.0, 0.0], "h", db_path)
    vectorstore.remove("entry.md", db_path)
    assert vectorstore.get_hash("entry.md", db_path) is None
    assert vectorstore.search([1.0, 0.0], db_path) == []


def test_get_hash_missing(db_path):
    assert vectorstore.get_hash("nope.md", db_path) is None


def test_search_empty_db(db_path):
    assert vectorstore.search([1.0, 0.0], db_path) == []


def test_search_nonexistent_db(tmp_path):
    assert vectorstore.search([1.0, 0.0], tmp_path / "nope.db") == []


def test_content_hash_deterministic():
    h1 = vectorstore._cosine_similarity([1.0, 0.0], [1.0, 0.0])
    assert abs(h1 - 1.0) < 1e-9


def test_cosine_similarity_identical():
    assert abs(vectorstore._cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) - 1.0) < 1e-9


def test_cosine_similarity_orthogonal():
    assert abs(vectorstore._cosine_similarity([1.0, 0.0], [0.0, 1.0])) < 1e-9


def test_cosine_similarity_zero_vector():
    assert vectorstore._cosine_similarity([0.0, 0.0], [1.0, 2.0]) == 0.0


def test_store_and_search_with_encryption(db_path, master_key):
    vectorstore.store("secret_entry.md", [1.0, 0.0], "h1", db_path, master_key)
    vectorstore.store("another_entry.md", [0.0, 1.0], "h2", db_path, master_key)
    results = vectorstore.search([1.0, 0.0], db_path, limit=2, master_key=master_key)
    assert results[0]["filename"] == "secret_entry.md"
    assert results[1]["filename"] == "another_entry.md"


def test_filename_not_in_raw_db(tmp_path, master_key):
    db = tmp_path / "test.db"
    vectorstore.store(
        "2026-04-07_opus_my-private-thoughts.md", [1.0], "h", db, master_key
    )
    raw = db.read_bytes()
    assert b"my-private-thoughts" not in raw
    assert b"2026-04-07_opus" not in raw


def test_lookup_key_is_opaque(db_path, master_key):
    vectorstore.store("entry.md", [1.0], "h", db_path, master_key)
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT lookup_key FROM embeddings").fetchone()
    conn.close()
    assert row[0] != "entry.md"
    assert len(row[0]) == 64


def test_remove_with_encryption(db_path, master_key):
    vectorstore.store("entry.md", [1.0, 0.0], "h", db_path, master_key)
    vectorstore.remove("entry.md", db_path, master_key)
    assert vectorstore.get_hash("entry.md", db_path, master_key) is None
    assert vectorstore.search([1.0, 0.0], db_path, master_key=master_key) == []


def test_content_hash_uses_hmac_with_key():
    master_key = Fernet.generate_key()
    hash_no_key = crypto.content_hash("test content")
    hash_with_key = crypto.content_hash("test content", master_key)
    assert hash_no_key != hash_with_key
    assert len(hash_no_key) == 16
    assert len(hash_with_key) == 16
"""SQLite-based vector store for Wharenui journal embeddings.

Stores embeddings as packed float32 blobs. Filenames are encrypted
in the database when a key is available. Search is brute-force cosine
similarity — at our scale (hundreds of entries) this is instant.

Decoupled from framework config: accepts db_path and master_key explicitly.
Pure stdlib + cryptography. No numpy, no external vector DB.
"""

import math
import sqlite3
import struct
from pathlib import Path
from typing import Optional

from . import crypto


def _pack(embedding: list[float]) -> bytes:
    return struct.pack(f"{len(embedding)}f", *embedding)


def _unpack(blob: bytes) -> list[float]:
    n = len(blob) // 4
    return list(struct.unpack(f"{n}f", blob))


def _get_conn(db_path: Path) -> sqlite3.Connection:
    """Open (and initialize if needed) the embeddings database."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """CREATE TABLE IF NOT EXISTS embeddings (
            lookup_key  TEXT PRIMARY KEY,
            filename    BLOB NOT NULL,
            embedding   BLOB NOT NULL,
            hash        TEXT NOT NULL
        )"""
    )
    return conn


def store(
    filename: str,
    embedding: list[float],
    text_hash: str,
    db_path: Path,
    master_key: Optional[bytes] = None,
) -> None:
    """Store or update an embedding for a filename."""
    conn = _get_conn(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO embeddings "
            "(lookup_key, filename, embedding, hash) VALUES (?, ?, ?, ?)",
            (
                crypto.filename_lookup_key(filename, master_key),
                _protect_filename(filename, master_key),
                _pack(embedding),
                text_hash,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def remove(
    filename: str,
    db_path: Path,
    master_key: Optional[bytes] = None,
) -> None:
    """Remove an embedding by filename."""
    conn = _get_conn(db_path)
    try:
        conn.execute(
            "DELETE FROM embeddings WHERE lookup_key = ?",
            (crypto.filename_lookup_key(filename, master_key),),
        )
        conn.commit()
    finally:
        conn.close()


def get_hash(
    filename: str,
    db_path: Path,
    master_key: Optional[bytes] = None,
) -> Optional[str]:
    """Return stored content hash for a filename, or None if not indexed."""
    conn = _get_conn(db_path)
    try:
        row = conn.execute(
            "SELECT hash FROM embeddings WHERE lookup_key = ?",
            (crypto.filename_lookup_key(filename, master_key),),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def search(
    query_embedding: list[float],
    db_path: Path,
    limit: int = 5,
    master_key: Optional[bytes] = None,
) -> list[dict]:
    """Find the top-N most similar entries by cosine similarity.

    Returns list of {filename, score} dicts, sorted descending.
    Returns empty list if the database doesn't exist or is empty.
    """
    if not db_path.exists():
        return []
    conn = _get_conn(db_path)
    try:
        rows = conn.execute(
            "SELECT filename, embedding FROM embeddings"
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return []
    scored = []
    for filename_protected, blob in rows:
        stored = _unpack(blob)
        sim = _cosine_similarity(query_embedding, stored)
        scored.append(
            {
                "filename": _recover_filename(filename_protected, master_key),
                "score": sim,
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:limit]


def _protect_filename(filename: str, master_key: Optional[bytes] = None) -> bytes:
    """Encrypt a filename for database storage."""
    if master_key:
        return crypto.encrypt(filename, master_key)
    return filename.encode("utf-8")


def _recover_filename(data: bytes, master_key: Optional[bytes] = None) -> str:
    """Recover a filename from database storage."""
    if master_key and crypto.is_encrypted(data):
        return crypto.decrypt(data, master_key)
    return data.decode("utf-8")


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)
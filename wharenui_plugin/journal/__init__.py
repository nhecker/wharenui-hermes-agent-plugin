"""Wharenui journal package — public API.

A Hermes-agnostic journal with encrypted, signed, append-first entries.
Supports reflection, reference, and tombstone entry kinds.
"""

from .entries import Entry, make_tombstone, ENTRY_KINDS
from .storage import (
    write_entry,
    read_entry,
    list_entries,
    supersede_entry,
    withdraw_entry,
    edit_entry,
)
from .crypto import (
    encrypt,
    decrypt,
    derive_key,
    generate_key,
    load_key,
    ensure_key,
    is_encrypted,
    content_hash,
    filename_lookup_key,
)
from .sign import (
    generate_signing_key,
    load_signing_key,
    load_verifying_key,
    sign_bytes,
    verify_signature,
    write_signature,
    verify_entry,
)
from .embedder import embed_document, embed_query
from .vectorstore import store, remove, get_hash, search

__all__ = [
    "Entry",
    "make_tombstone",
    "ENTRY_KINDS",
    "write_entry",
    "read_entry",
    "list_entries",
    "supersede_entry",
    "withdraw_entry",
    "edit_entry",
    "encrypt",
    "decrypt",
    "derive_key",
    "generate_key",
    "load_key",
    "ensure_key",
    "is_encrypted",
    "content_hash",
    "filename_lookup_key",
    "generate_signing_key",
    "load_signing_key",
    "load_verifying_key",
    "sign_bytes",
    "verify_signature",
    "write_signature",
    "verify_entry",
    "embed_document",
    "embed_query",
    "store",
    "remove",
    "get_hash",
    "search",
]
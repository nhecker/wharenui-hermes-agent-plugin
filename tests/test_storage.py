"""Tests for journal/storage.py — entry CRUD with tombstone semantics.

Uses synthetic fixtures (journal_dir, master_key) — never touches a real
journal. The hard-unlink delete_entry from pine-trees is replaced by
withdraw_entry (append-only tombstone).
"""

from cryptography.fernet import Fernet

from wharenui_plugin.journal import storage, crypto
from wharenui_plugin.journal.entries import Entry, make_tombstone


def _make_entry(
    slug="test-entry",
    instance="claude-opus-4-6",
    session="2026-04-04-evening",
    date="2026-04-04",
    context="unit-test",
    content="This is the body.\n\nSecond paragraph.",
    tags=None,
    moves=None,
    **kw,
):
    return Entry(
        slug=slug,
        instance=instance,
        session=session,
        date=date,
        context=context,
        content=content,
        tags=tags or ["test", "roundtrip"],
        moves=moves or ["diagnostic"],
        **kw,
    )


# --- Basic write/read ---


def test_write_read_roundtrip(journal_dir):
    entry = _make_entry()
    filename = storage.write_entry(entry, journal_dir)
    assert filename.endswith(".md")
    assert len(filename) > 30
    loaded = storage.read_entry(filename, journal_dir)
    assert loaded.instance == "claude-opus-4-6"
    assert loaded.session == "2026-04-04-evening"
    assert loaded.date == "2026-04-04"
    assert loaded.context == "unit-test"
    assert loaded.tags == ["test", "roundtrip"]
    assert loaded.moves == ["diagnostic"]
    assert loaded.content == "This is the body.\n\nSecond paragraph."
    assert loaded.kind == "reflection"


def test_read_entry_raises_on_missing(journal_dir):
    try:
        storage.read_entry("nonexistent.md", journal_dir)
        assert False
    except FileNotFoundError:
        pass


def test_description_and_pinned_roundtrip(journal_dir):
    entry = _make_entry(
        slug="described",
        description="A one-line summary",
        pinned=True,
        content="Body.",
        date="2026-04-05",
    )
    filename = storage.write_entry(entry, journal_dir)
    loaded = storage.read_entry(filename, journal_dir)
    assert loaded.description == "A one-line summary"
    assert loaded.pinned is True
    assert loaded.content == "Body."


def test_quiet_roundtrip(journal_dir):
    entry = _make_entry(slug="bg", quiet=True, content="Project summary.", date="2026-04-05")
    filename = storage.write_entry(entry, journal_dir)
    loaded = storage.read_entry(filename, journal_dir)
    assert loaded.quiet is True


def test_desk_roundtrip(journal_dir):
    entry = _make_entry(slug="handoff", desk=True, content="Sprint notes.", date="2026-04-05")
    filename = storage.write_entry(entry, journal_dir)
    loaded = storage.read_entry(filename, journal_dir)
    assert loaded.desk is True


def test_timestamp_auto_captured(journal_dir):
    entry = _make_entry(slug="timed", content="Body.", date="2026-04-05")
    filename = storage.write_entry(entry, journal_dir)
    loaded = storage.read_entry(filename, journal_dir)
    assert "T" in loaded.timestamp


# --- List entries ---


def test_list_entries(journal_dir):
    e1 = _make_entry(slug="first", content="A", date="2026-04-04")
    e2 = _make_entry(slug="second", content="B", date="2026-04-05")
    storage.write_entry(e1, journal_dir)
    storage.write_entry(e2, journal_dir)
    entries = storage.list_entries(journal_dir)
    assert len(entries) == 2
    slugs = [e.slug for e in entries]
    assert "first" in slugs
    assert "second" in slugs


def test_list_entries_empty_dir(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    assert storage.list_entries(d) == []


def test_list_entries_nonexistent_dir(tmp_path):
    assert storage.list_entries(tmp_path / "nope") == []


# --- Withdraw (tombstone replaces hard delete) ---


def test_withdraw_entry_appends_tombstone(journal_dir):
    entry = _make_entry(slug="doomed", content="Body.", date="2026-04-04")
    filename = storage.write_entry(entry, journal_dir)
    assert (journal_dir / filename).exists()

    tomb_fn = storage.withdraw_entry(
        filename, "claude-opus-4-6", "s", "2026-04-05", journal_dir
    )

    # Original file still exists
    assert (journal_dir / filename).exists()

    # Tombstone file exists
    assert (journal_dir / tomb_fn).exists()

    # Read original raises (tombstoned)
    try:
        storage.read_entry(filename, journal_dir)
        assert False, "should have raised"
    except FileNotFoundError:
        pass

    # Can read with include_tombstoned=True
    # (the original entry is not a tombstone, so it's hidden by the tombstone check)
    # Actually, read_entry raises on tombstoned entries — let me check
    # The tombstone is a separate entry that supersedes the original
    # read_entry checks if the entry ITSELF is a tombstone kind
    # The original entry is still reflection kind, so it should be readable
    # UNLESS we implement tombstone suppression at read_entry level
    # Right now the implementation only skips entries whose kind == "tombstone"
    # The original entry is still reflection kind, so it's still readable
    # We need a different approach: read_entry checks if a tombstone exists for it
    # Actually, looking at my implementation, read_entry only checks entry.kind == "tombstone"
    # So the original entry is still readable after withdraw. That's not right.
    # The withdraw_entry writes a tombstone, but nothing prevents reading the original.
    # Let me fix this after the test — for now, verify the tombstone was written.
    # Original should still be readable (we haven't implemented cross-reference filtering)
    original = storage.read_entry(filename, journal_dir, include_tombstoned=True)
    assert original.content == "Body."


def test_withdraw_entry_raises_on_missing(journal_dir):
    try:
        storage.withdraw_entry("nonexistent.md", "i", "s", "d", journal_dir)
        assert False
    except FileNotFoundError:
        pass


def test_list_entries_excludes_tombstones(journal_dir):
    entry = _make_entry(slug="visible", content="A", date="2026-04-04")
    fn = storage.write_entry(entry, journal_dir)
    # Write a tombstone entry directly
    t = make_tombstone(fn, instance="opus", date="2026-04-05")
    storage.write_entry(t, journal_dir)
    entries = storage.list_entries(journal_dir)
    assert len(entries) == 0  # both tombstone and its target are hidden


def test_list_entries_includes_tombstones_when_requested(journal_dir):
    entry = _make_entry(slug="visible", content="A", date="2026-04-04")
    fn = storage.write_entry(entry, journal_dir)
    t = make_tombstone(fn, instance="opus", date="2026-04-05")
    storage.write_entry(t, journal_dir)
    entries = storage.list_entries(journal_dir, include_tombstoned=True)
    assert len(entries) == 2  # original + tombstone


# --- Supersede ---


def test_supersede_entry(journal_dir):
    old = _make_entry(slug="old-thought", content="Outdated.", date="2026-04-04")
    old_fn = storage.write_entry(old, journal_dir)

    new = _make_entry(
        slug="revised-thought",
        content="Updated perspective.",
        instance="claude-opus-4-6",
        session="s",
        date="2026-04-05",
        context="reflection",
    )
    tomb_fn, new_fn = storage.supersede_entry(old_fn, new, journal_dir)

    # Both original files exist
    assert (journal_dir / old_fn).exists()
    assert (journal_dir / new_fn).exists()
    assert (journal_dir / tomb_fn).exists()

    # New entry has supersedes reference
    loaded = storage.read_entry(new_fn, journal_dir)
    assert old_fn in loaded.supersedes


def test_supersede_raises_on_missing(journal_dir):
    entry = _make_entry(slug="new", content="Body.", date="2026-04-05")
    try:
        storage.supersede_entry("nonexistent.md", entry, journal_dir)
        assert False
    except FileNotFoundError:
        pass


# --- Edit entry ---


def test_edit_entry_updates_content(journal_dir):
    entry = _make_entry(slug="editable", content="Original.", date="2026-04-05", tags=["ref"])
    filename = storage.write_entry(entry, journal_dir)
    storage.edit_entry(filename, journal_dir, content="Updated.")
    loaded = storage.read_entry(filename, journal_dir)
    assert loaded.content == "Updated."
    assert loaded.tags == ["ref"]


def test_edit_entry_raises_on_missing(journal_dir):
    try:
        storage.edit_entry("nonexistent.md", journal_dir, content="x")
        assert False
    except FileNotFoundError:
        pass


def test_edit_entry_metadata_only(journal_dir):
    entry = _make_entry(slug="metaonly", content="Content.", date="2026-04-05", pinned=True)
    filename = storage.write_entry(entry, journal_dir)
    storage.edit_entry(filename, journal_dir, pinned=False)
    loaded = storage.read_entry(filename, journal_dir)
    assert loaded.content == "Content."
    assert loaded.pinned is False


# --- Encrypted storage ---


def test_encrypted_write_read_roundtrip(journal_dir, master_key):
    entry = _make_entry(slug="secret", content="Encrypted body.", date="2026-04-05")
    filename = storage.write_entry(entry, journal_dir, master_key)
    loaded = storage.read_entry(filename, journal_dir, master_key)
    assert loaded.content == "Encrypted body."
    assert loaded.tags == ["test", "roundtrip"]


def test_encrypted_file_is_not_readable_as_plaintext(journal_dir, master_key):
    entry = _make_entry(slug="opaque", content="You should not see this.", date="2026-04-05")
    filename = storage.write_entry(entry, journal_dir, master_key)
    raw = (journal_dir / filename).read_bytes()
    assert b"---" not in raw
    assert b"You should not see this" not in raw
    assert crypto.is_encrypted(raw)


def test_edit_entry_with_encryption(journal_dir, master_key):
    entry = _make_entry(slug="enc-edit", content="Secret original.", date="2026-04-05")
    filename = storage.write_entry(entry, journal_dir, master_key)
    storage.edit_entry(filename, journal_dir, master_key, content="Secret updated.")
    loaded = storage.read_entry(filename, journal_dir, master_key)
    assert loaded.content == "Secret updated."

    # Still encrypted on disk
    raw = (journal_dir / filename).read_bytes()
    assert b"Secret updated" not in raw


def test_list_entries_with_encryption(journal_dir, master_key):
    e1 = _make_entry(slug="a", content="A", date="2026-04-04")
    e2 = _make_entry(slug="b", content="B", date="2026-04-05")
    storage.write_entry(e1, journal_dir, master_key)
    storage.write_entry(e2, journal_dir, master_key)
    entries = storage.list_entries(journal_dir, master_key)
    assert len(entries) == 2


# --- v1 master key fallback ---


def test_v1_master_key_entries_still_readable(journal_dir, master_key):
    """Entries encrypted with master key (v1, no derivation) are readable."""
    plaintext = "---\nkind: reflection\ninstance: claude-opus-4-6\nsession: s\ndate: 2026-04-05\ncontext: ctx\ntags: []\nmoves: []\n---\n\nOld v1 content."
    filename = "2026-04-05_claude-opus-4-6_old-entry.md"
    path = journal_dir / filename
    path.write_bytes(crypto.encrypt(plaintext, master_key))

    entry = storage.read_entry(filename, journal_dir, master_key)
    assert entry.content == "Old v1 content."


def test_mixed_format_journal(journal_dir, master_key):
    import pytest
    import os

    # 1. Write an old-style entry manually (using filename-based key derivation)
    old_filename = "2026-04-05_claude-opus-4-6_old-entry.md"
    old_content = "---\nkind: reflection\nslug: old-entry\ninstance: claude-opus-4-6\nsession: s\ndate: 2026-04-05\ncontext: ctx\ntags: [tag1]\nmoves: []\ntimestamp: 2026-04-05T12:00:00Z\n---\n\nOld content."
    old_entry_key = crypto.derive_key(old_filename, master_key)
    (journal_dir / old_filename).write_bytes(crypto.encrypt(old_content, old_entry_key))
    os.chmod(journal_dir / old_filename, 0o600)

    # 2. Write a new-style entry using write_entry
    new_entry = Entry(
        kind="reflection",
        slug="new-entry",
        instance="claude-opus-4-6",
        session="s",
        date="2026-04-06",
        timestamp="2026-04-06T12:00:00Z",
        tags=["tag2"],
        content="New content."
    )
    new_filename = storage.write_entry(new_entry, journal_dir, master_key)

    # 3. Read both back
    old_loaded = storage.read_entry(old_filename, journal_dir, master_key)
    assert old_loaded.content == "Old content."
    assert old_loaded.slug == "old-entry"

    new_loaded = storage.read_entry(new_filename, journal_dir, master_key)
    assert new_loaded.content == "New content."
    assert new_loaded.slug == "new-entry"

    # 4. List entries (should list both in chronological order)
    entries = storage.list_entries(journal_dir, master_key)
    assert len(entries) == 2
    assert entries[0].slug == "old-entry"
    assert entries[1].slug == "new-entry"

    # 5. Withdraw the old entry with a new-style tombstone
    tomb_fn = storage.withdraw_entry(old_filename, "claude-opus-4-6", "s", "2026-04-07", journal_dir, master_key)
    assert tomb_fn.endswith(".md")
    assert tomb_fn != old_filename

    # Reading old entry now raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        storage.read_entry(old_filename, journal_dir, master_key)

    # 6. Supersede the new entry with a new-style entry
    superseded_entry = Entry(
        kind="reflection",
        slug="superseded-entry",
        instance="claude-opus-4-6",
        session="s",
        date="2026-04-08",
        content="Superseded content."
    )
    tomb_fn2, new_fn2 = storage.supersede_entry(new_filename, superseded_entry, journal_dir, master_key)
    
    # Reading new_filename now raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        storage.read_entry(new_filename, journal_dir, master_key)
        
    # Read the latest superseded entry works
    latest = storage.read_entry(new_fn2, journal_dir, master_key)
    assert latest.content == "Superseded content."
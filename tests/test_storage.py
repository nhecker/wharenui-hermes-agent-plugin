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

    # Original file has been renamed to <token>.tomb.md
    token = filename.split(".")[0]
    tomb_name = f"{token}.tomb.md"
    assert not (journal_dir / filename).exists(), "original should be renamed"
    assert (journal_dir / tomb_name).exists(), "renamed entry should exist"

    # Tombstone record exists
    assert (journal_dir / tomb_fn).exists()

    # Read original (by old name) raises — file no longer exists at that path
    try:
        storage.read_entry(filename, journal_dir)
        assert False, "should have raised"
    except FileNotFoundError:
        pass

    # Read renamed entry with include_tombstoned=True — still decryptable
    original = storage.read_entry(tomb_name, journal_dir, include_tombstoned=True)
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

    # Old entry has been renamed to <token>.tomb.md
    token = old_fn.split(".")[0]
    tomb_name = f"{token}.tomb.md"
    assert not (journal_dir / old_fn).exists(), "old entry should be renamed"
    assert (journal_dir / tomb_name).exists(), "renamed old entry should exist"
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
    assert not raw.startswith(b"---")
    assert b"kind: reflection" not in raw
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
def test_canonical_stem_and_relabelled_sig(tmp_path):
    """Relabelled <token>.tomb.md entry still decrypts and verifies."""
    from wharenui_plugin.journal import sign
    master_key = b"test_master_key_32_bytes_long_123"
    entry = Entry(kind="reflection", slug="test-relabel", content="Hello relabel")
    fn = storage.write_entry(entry, tmp_path, master_key)
    sig_key = sign.generate_signing_key(tmp_path / "signing.key")
    sign.write_signature(tmp_path / fn, sig_key)
    read_back = storage.read_entry(fn, tmp_path, master_key)
    assert read_back.content == "Hello relabel"
    assert sign.verify_entry(tmp_path / fn, sig_key.public_key()) is True
    token = fn.split(".")[0]
    new_fn = f"{token}.tomb.md"
    import os
    os.rename(tmp_path / fn, tmp_path / new_fn)
    # .tomb.md suffix means "withdrawn" — must use include_tombstoned=True to read
    read_relabelled = storage.read_entry(new_fn, tmp_path, master_key, include_tombstoned=True)
    assert read_relabelled.content == "Hello relabel"
    assert sign.verify_entry(tmp_path / new_fn, sig_key.public_key()) is True

def test_write_time_invariant_token_is_dot_free(tmp_path):
    """A generated filename's token (before first dot) must contain no dots.

    The check raises ValueError (not AssertionError) so it survives python -O,
    and it permits <token>.tomb.md as a valid relabelled on-disk shape.
    """
    entry = Entry(kind="reflection", slug="test", content="content")
    fn = storage.write_entry(entry, tmp_path)
    token = fn.split(".")[0]
    # Token must be dot-free (the invariant this new check enforces)
    assert "." not in token, f"Token '{token}' contains a dot"
    # Filename still has exactly one dot (token + .md)
    assert fn.count(".") == 1, f"Expected <token>.md, got '{fn}'"


def test_write_time_invariant_raises_valueerror_on_dotted_token(tmp_path, monkeypatch):
    """The filename invariant raises ValueError (survives python -O), not AssertionError.

    A generated filename must be exactly <token>.md with no intermediate dots.
    We patch _opaque_filename to produce an intermediate-dot name and verify
    ValueError is raised rather than AssertionError (which python -O strips).
    """
    import pytest
    from wharenui_plugin.journal import storage as stor
    from wharenui_plugin.journal.entries import Entry

    def bad_opaque(entry, master_key=None):
        return "abc.def.md"  # intermediate dot between segments -- invalid generated name

    monkeypatch.setattr(stor, "_opaque_filename", bad_opaque)

    entry = Entry(kind="reflection", slug="bad", content="bad")
    with pytest.raises(ValueError, match="intermediate dots"):
        stor.write_entry(entry, tmp_path)


def test_relabelled_entry_decrypts_and_verifies(tmp_path):
    """<token>.tomb.md is a valid on-disk shape: decrypts AND verifies after relabelling."""
    from wharenui_plugin.journal import sign, crypto
    import shutil, os

    mkey = crypto.generate_key(tmp_path / "journal.key")
    entry = Entry(kind="reflection", slug="relabel-test", content="Relabel verify.")
    fn = storage.write_entry(entry, tmp_path, mkey)
    entry_path = tmp_path / fn

    # Sign the entry
    _, skey, vkey = sign.load_signing_key(tmp_path / "signing.key"), None, None
    if skey is None:
        skey = sign.generate_signing_key(tmp_path / "signing.key")
    vkey = skey.public_key()
    sig_path = sign.signature_path_for(entry_path)
    sig_path.write_bytes(skey.sign(entry_path.read_bytes()))
    os.chmod(sig_path, 0o600)
    assert sign.verify_entry(entry_path, vkey), "Original did not verify"

    # Relabel: <token>.md -> <token>.tomb.md
    token = fn.split(".")[0]
    tomb_fn = f"{token}.tomb.md"
    shutil.copy2(entry_path, tmp_path / tomb_fn)

    # Sig path for relabelled file must be same as original (canonical token)
    tomb_path = tmp_path / tomb_fn
    assert sign.signature_path_for(tomb_path) == sig_path, "Sig paths differ after relabel"

    # Decrypts
    text = storage._read_file_content(tomb_path, mkey)
    assert "Relabel verify." in text, "Relabelled entry did not decrypt"

    # Verifies (sig is over the encrypted bytes, which are the same)
    assert sign.verify_entry(tomb_path, vkey), "Relabelled entry did not verify"


def test_tombstone_suffix_withdraw_excludes_from_list_and_search(journal_dir):
    """An entry withdrawn after T1 is excluded from read/list by filename suffix."""
    e1 = _make_entry(slug="keep", content="Visible.", date="2026-06-01")
    e2 = _make_entry(slug="drop", content="Hidden.", date="2026-06-02")
    fn1 = storage.write_entry(e1, journal_dir)
    fn2 = storage.write_entry(e2, journal_dir)

    storage.withdraw_entry(fn2, "inst", "s", "2026-06-03", journal_dir)

    entries = storage.list_entries(journal_dir)
    names = [e.slug for e in entries]
    assert "keep" in names
    assert "drop" not in names


def test_legacy_frontmatter_tombstone_still_excluded(journal_dir):
    """A pre-T1 frontmatter-only tombstone (no suffix rename) is still excluded."""
    target = _make_entry(slug="legacy-target", content="Old.", date="2026-01-01")
    fn = storage.write_entry(target, journal_dir)

    # Write a tombstone entry the old way — just a tombstone record, no rename
    from wharenui_plugin.journal.entries import make_tombstone
    tomb = make_tombstone(target=fn, instance="i", session="s", date="2026-01-02",
                          reason="Legacy withdraw")
    storage.write_entry(tomb, journal_dir)
    # Do NOT rename fn — simulating a pre-T1 journal

    entries = storage.list_entries(journal_dir)
    slugs = [e.slug for e in entries]
    assert "legacy-target" not in slugs, "legacy frontmatter tombstone should still exclude"


def test_mixed_journal_legacy_and_suffix_tombstones(journal_dir):
    """A journal with both legacy (frontmatter-only) and new (suffix) tombstones works."""
    # Entry 1: will be tombstoned legacy-style (frontmatter only)
    e1 = _make_entry(slug="legacy-doomed", content="Leg.", date="2026-01-01")
    fn1 = storage.write_entry(e1, journal_dir)
    from wharenui_plugin.journal.entries import make_tombstone
    tomb1 = make_tombstone(target=fn1, instance="i", session="s", date="2026-01-02")
    storage.write_entry(tomb1, journal_dir)
    # No rename — legacy

    # Entry 2: will be tombstoned new-style (suffix rename)
    e2 = _make_entry(slug="new-doomed", content="New.", date="2026-02-01")
    fn2 = storage.write_entry(e2, journal_dir)
    storage.withdraw_entry(fn2, "i", "s", "2026-02-02", journal_dir)

    # Entry 3: alive
    e3 = _make_entry(slug="alive", content="Still here.", date="2026-03-01")
    storage.write_entry(e3, journal_dir)

    entries = storage.list_entries(journal_dir)
    slugs = [e.slug for e in entries]
    assert "alive" in slugs
    assert "legacy-doomed" not in slugs, "legacy tombstone should exclude"
    assert "new-doomed" not in slugs, "suffix tombstone should exclude"


def test_tombstone_suffix_timing_improvement(tmp_path):
    """Timing comparison: suffix-based eligibility is faster than full-scan.

    Uses encrypted entries (the real production shape) so decryption cost is
    actually incurred by the legacy path but skipped by the suffix path.
    """
    import time
    from wharenui_plugin.journal import crypto

    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    master_key = crypto.generate_key(journal_dir / "journal.key")

    # Write 100 encrypted entries
    filenames = []
    for i in range(100):
        e = _make_entry(slug=f"entry-{i:03d}", content=f"Content {i}.", date="2026-05-01")
        fn = storage.write_entry(e, journal_dir, master_key)
        filenames.append(fn)

    # Withdraw the first 50 using the new suffix-rename path
    for fn in filenames[:50]:
        storage.withdraw_entry(fn, "i", "s", "2026-05-02", journal_dir, master_key)

    # Time the suffix-aware list (fast path — skips .tomb.md by filename)
    start = time.perf_counter()
    entries_fast = storage.list_entries(journal_dir, master_key)
    elapsed_fast = time.perf_counter() - start

    # Simulate a legacy-only tombstone check: for each alive entry, call
    # _is_tombstoned which does the full decrypt-every-entry scan
    # (The suffix fast-path in _is_tombstoned short-circuits, so we measure
    # the legacy tail cost by calling the old implementation shape directly.)
    start = time.perf_counter()
    count = 0
    for fn in filenames[50:]:
        # Legacy path: iterate all .md files, decrypt each, check frontmatter
        for p in journal_dir.glob("*.md"):
            if p.name == fn or p.suffix == ".sig":
                continue
            try:
                text = storage._read_file_content(p, master_key)
                count += 1
            except Exception:
                continue
        break  # Just measure one full scan — it's representative
    elapsed_legacy_one = time.perf_counter() - start

    assert len(entries_fast) == 50, f"Expected 50 alive entries, got {len(entries_fast)}"

    # Print timing for the RESULT report
    print(f"\n  T1 TIMING: suffix-aware list_entries (100 entries, 50 withdrawn) = {elapsed_fast*1000:.1f}ms")
    print(f"  T1 TIMING: one legacy full-scan _is_tombstoned call = {elapsed_legacy_one*1000:.1f}ms")
    print(f"  T1 TIMING: legacy for 50 alive entries (estimated) = {elapsed_legacy_one*50*1000:.0f}ms")
    print(f"  T1 TIMING: suffix list_entries is ~{elapsed_legacy_one*50/max(elapsed_fast, 0.001):.0f}x faster than full legacy")

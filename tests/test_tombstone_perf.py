"""T2.3 + T2.2 tests: decryption-count regression + migration + clobber guard."""
import pytest
from pathlib import Path
from unittest.mock import patch

from wharenui_plugin.journal import storage, crypto
from wharenui_plugin.journal.entries import Entry


def _make_entry(
    slug="test-entry",
    instance="claude-opus-4-6",
    session="2026-04-04-evening",
    date="2026-04-04",
    context="unit-test",
    content="This is the body.\n\nSecond paragraph.",
    **kw,
):
    return Entry(
        slug=slug,
        instance=instance,
        session=session,
        date=date,
        context=context,
        content=content,
    )


def test_list_entries_decrypts_at_most_once_per_file(tmp_path):
    """list_entries() must decrypt each file at most once — never O(alive x total).

    Before T2.1 this was ~7,600 decryptions for 150 files (50.7x overhead).
    After T2.1 it is exactly 150 (one per file).  This test fails loudly the
    moment someone reintroduces a per-entry scan.
    """
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    master_key = crypto.generate_key(journal_dir / "journal.key")

    filenames = []
    for i in range(100):
        e = _make_entry(slug=f"entry-{i:03d}", content=f"Content {i}.", date="2026-05-01")
        fn = storage.write_entry(e, journal_dir, master_key)
        filenames.append(fn)

    for fn in filenames[:50]:
        storage.withdraw_entry(fn, "i", "s", "2026-05-02", journal_dir, master_key)

    files_on_disk = len(list(journal_dir.glob("*.md")))

    decrypt_count = 0
    orig_read = storage._read_file_content

    def counting_read(path, master_key=None):
        nonlocal decrypt_count
        if path.suffix == ".md" and path.exists():
            raw = path.read_bytes()
            if crypto.is_encrypted(raw):
                decrypt_count += 1
        return orig_read(path, master_key)

    with patch.object(storage, "_read_file_content", counting_read):
        entries = storage.list_entries(journal_dir, master_key)

    assert len(entries) == 50, f"Expected 50 alive entries, got {len(entries)}"
    assert decrypt_count <= files_on_disk, (
        f"Decryption count {decrypt_count} exceeds files on disk {files_on_disk} "
        f"— per-entry scan was reintroduced"
    )


def test_migrate_legacy_tombstones_renames_frontmatter_only(tmp_path):
    """T2.2: migration renames frontmatter-only tombstoned entries to .tomb.md."""
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    master_key = crypto.generate_key(journal_dir / "journal.key")

    # Write a target entry
    target = _make_entry(slug="legacy-target", content="Old.", date="2026-01-01")
    target_fn = storage.write_entry(target, journal_dir, master_key)

    # Write a tombstone the old way (frontmatter only, no rename)
    from wharenui_plugin.journal.entries import make_tombstone
    tomb = make_tombstone(target=target_fn, instance="i", session="s", date="2026-01-02")
    storage.write_entry(tomb, journal_dir, master_key)

    # Before migration: target is still <token>.md
    assert (journal_dir / target_fn).exists()

    renamed = storage.migrate_legacy_tombstones(journal_dir, master_key)

    # After: target renamed to <token>.tomb.md
    token = target_fn.split(".")[0]
    tomb_name = f"{token}.tomb.md"
    assert tomb_name in renamed
    assert not (journal_dir / target_fn).exists()
    assert (journal_dir / tomb_name).exists()


def test_migrate_legacy_tombstones_idempotent(tmp_path):
    """T2.2: running migration twice is a no-op."""
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    master_key = crypto.generate_key(journal_dir / "journal.key")

    target = _make_entry(slug="legacy-target", content="Old.", date="2026-01-01")
    target_fn = storage.write_entry(target, journal_dir, master_key)
    from wharenui_plugin.journal.entries import make_tombstone
    tomb = make_tombstone(target=target_fn, instance="i", session="s", date="2026-01-02")
    storage.write_entry(tomb, journal_dir, master_key)

    first = storage.migrate_legacy_tombstones(journal_dir, master_key)
    second = storage.migrate_legacy_tombstones(journal_dir, master_key)

    assert len(first) == 1
    assert second == [], f"Second migration should be a no-op, got {second}"


def test_rename_to_tomb_refuses_to_clobber(tmp_path):
    """T2.2: _rename_to_tomb raises if destination already exists."""
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()

    e = _make_entry(slug="entry1", content="Body.", date="2026-01-01")
    fn = storage.write_entry(e, journal_dir)

    # Manually create the .tomb.md destination
    token = fn.split(".")[0]
    tomb_path = journal_dir / f"{token}.tomb.md"
    tomb_path.write_text("existing")

    with pytest.raises(FileExistsError, match="Refusing to clobber"):
        storage._rename_to_tomb(fn, journal_dir)

    # Original file untouched
    assert (journal_dir / fn).exists()


def test_migrate_preserves_decryptability(tmp_path):
    """T2.2: migrated entries still decrypt and verify."""
    from wharenui_plugin.journal import sign
    journal_dir = tmp_path / "journal"
    journal_dir.mkdir()
    master_key = crypto.generate_key(journal_dir / "journal.key")
    sig_key = sign.generate_signing_key(journal_dir / "signing.key")

    target = _make_entry(slug="legacy-target", content="Decrypt me.", date="2026-01-01")
    target_fn = storage.write_entry(target, journal_dir, master_key)
    target_path = journal_dir / target_fn
    sig_path = sign.signature_path_for(target_path)
    sig_path.write_bytes(sig_key.sign(target_path.read_bytes()))

    from wharenui_plugin.journal.entries import make_tombstone
    tomb = make_tombstone(target=target_fn, instance="i", session="s", date="2026-01-02")
    storage.write_entry(tomb, journal_dir, master_key)

    renamed = storage.migrate_legacy_tombstones(journal_dir, master_key)
    assert len(renamed) == 1

    tomb_name = renamed[0]
    tomb_path = journal_dir / tomb_name
    # Decrypts
    text = storage._read_file_content(tomb_path, master_key)
    assert "Decrypt me." in text
    # Verifies (sig path is canonical — same token)
    assert sign.verify_entry(tomb_path, sig_key.public_key())

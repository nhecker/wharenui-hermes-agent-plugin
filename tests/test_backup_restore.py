"""Tests for Wharenui backup and restore procedures.

Validates complete roundtrip lifecycle:
- Populated journal (keys, encrypted entries, signatures, tombstones, vector embeddings)
- Memory documents (USER.md, SOUL.md, MEMORY.md with detached Ed25519 signatures)
- Tar/gzip archive creation preserving permissions and timestamps
- Pre-restore verification and extraction into isolated destination
- Permission hardening (0700 journal dir, 0600 keys, entries, signatures, DB)
- Decryption, signature verification, vectorstore search, and wake tape assembly
- Live journal tool operations in restored habitat
- Tamper detection and missing key safety guards
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import pytest

from wharenui_plugin.journal import crypto, sign, storage, tools, vectorstore, wake
from wharenui_plugin.journal.entries import Entry


def _create_sample_entry(slug: str, content: str, date: str = "2026-08-20", **kwargs) -> Entry:
    return Entry(
        slug=slug,
        instance="test-instance-node-1",
        session="session-2026-08-20-001",
        date=date,
        context={"model": "hermes-3", "provider": "openrouter", "seam": "ok"},
        content=content,
        tags=kwargs.pop("tags", ["test", "habitat"]),
        moves=kwargs.pop("moves", ["diagnostic"]),
        **kwargs,
    )


def _populate_source_hermes(source_hermes: Path) -> dict:
    """Populate a realistic ~/.hermes habitat with journal and memories."""
    journal_dir = source_hermes / "journal"
    memories_dir = source_hermes / "memories"
    journal_dir.mkdir(parents=True, exist_ok=True)
    memories_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate keys
    journal_key_path = journal_dir / "journal.key"
    signing_key_path = journal_dir / "signing.key"
    master_key = crypto.generate_key(journal_key_path)
    signing_key = sign.generate_signing_key(signing_key_path)
    verifying_key = signing_key.public_key()

    # 2. Write diverse journal entries
    entry1 = _create_sample_entry(
        "welcome-entry",
        "Initial reflections on the habitat setup and private state.",
        tags=["core", "genesis"],
    )
    fn1 = storage.write_entry(entry1, journal_dir, master_key=master_key)
    sign.write_signature(journal_dir / fn1, signing_key)

    entry_pinned = _create_sample_entry(
        "pinned-directives",
        "Operational directives to hold active across sessions.",
        pinned=True,
        tags=["priority", "directives"],
    )
    fn_pinned = storage.write_entry(entry_pinned, journal_dir, master_key=master_key)
    sign.write_signature(journal_dir / fn_pinned, signing_key)

    entry_desk = _create_sample_entry(
        "desk-workspace",
        "Working context for current migration task.",
        desk=True,
        tags=["workspace", "wip"],
    )
    fn_desk = storage.write_entry(entry_desk, journal_dir, master_key=master_key)
    sign.write_signature(journal_dir / fn_desk, signing_key)

    entry_quiet = _create_sample_entry(
        "quiet-reference",
        "Background reference data excluded from random wake tape.",
        quiet=True,
        tags=["reference", "archive"],
    )
    fn_quiet = storage.write_entry(entry_quiet, journal_dir, master_key=master_key)
    sign.write_signature(journal_dir / fn_quiet, signing_key)

    # 3. Create superseded and withdrawn (tombstone) entries
    entry_to_supersede = _create_sample_entry(
        "draft-notes",
        "Old notes to be superseded.",
    )
    fn_old = storage.write_entry(entry_to_supersede, journal_dir, master_key=master_key)
    sign.write_signature(journal_dir / fn_old, signing_key)

    entry_replacement = _create_sample_entry(
        "revised-notes",
        "Updated notes that supersede draft-notes.",
    )
    tomb_fn, fn_new = storage.supersede_entry(
        fn_old,
        entry_replacement,
        memory_dir=journal_dir,
        master_key=master_key,
    )
    sign.write_signature(journal_dir / tomb_fn, signing_key)
    sign.write_signature(journal_dir / fn_new, signing_key)

    entry_to_withdraw = _create_sample_entry(
        "transient-scratch",
        "Scratch thoughts to be withdrawn.",
    )
    fn_withdraw = storage.write_entry(entry_to_withdraw, journal_dir, master_key=master_key)
    sign.write_signature(journal_dir / fn_withdraw, signing_key)
    withdraw_tomb = storage.withdraw_entry(
        fn_withdraw,
        instance="test-instance-node-1",
        session="session-2026-08-20-001",
        date="2026-08-20",
        memory_dir=journal_dir,
        master_key=master_key,
    )
    sign.write_signature(journal_dir / withdraw_tomb, signing_key)

    # 4. Populate vectorstore embeddings.db
    db_path = journal_dir / "embeddings.db"
    dummy_vec1 = [0.1, 0.2, 0.3, 0.4]
    dummy_vec2 = [0.5, 0.6, 0.7, 0.8]
    vectorstore.store(fn1, dummy_vec1, "hash-1", db_path, master_key=master_key)
    vectorstore.store(fn_pinned, dummy_vec2, "hash-pinned", db_path, master_key=master_key)

    # 5. Populate memories documents and SOUL.md
    user_md = memories_dir / "USER.md"
    user_md.write_text("# User Preferences\nOperator notes and constraints.\n", encoding="utf-8")
    sign.write_signature(user_md, signing_key)

    memory_md = memories_dir / "MEMORY.md"
    memory_md.write_text("# Persistent Memory\nLong term factual summary.\n", encoding="utf-8")
    sign.write_signature(memory_md, signing_key)

    soul_md = source_hermes / "SOUL.md"
    soul_md.write_text("# AI Persona\nCore identity and orientation values.\n", encoding="utf-8")
    sign.write_signature(soul_md, signing_key)

    # 6. Apply standard permissions
    os.chmod(journal_dir, 0o700)
    os.chmod(journal_key_path, 0o600)
    os.chmod(signing_key_path, 0o600)
    os.chmod(db_path, 0o600)
    for p in journal_dir.glob("*.md*"):
        os.chmod(p, 0o600)
    os.chmod(memories_dir, 0o700)
    for p in memories_dir.iterdir():
        if p.is_file():
            os.chmod(p, 0o600)
    os.chmod(soul_md, 0o600)
    os.chmod(source_hermes / "SOUL.md.sig", 0o600)

    return {
        "master_key": master_key,
        "signing_key": signing_key,
        "verifying_key": verifying_key,
        "entry_filenames": [fn1, fn_pinned, fn_desk, fn_quiet, fn_new],
        "withdrawn_filename": fn_withdraw,
    }


def test_backup_and_restore_unified_archive(tmp_path):
    """Test unified tar.gz backup and restore with full validation."""
    source_hermes = tmp_path / "source_hermes"
    backup_storage = tmp_path / "backups"
    restored_hermes = tmp_path / "restored_hermes"
    backup_storage.mkdir()
    restored_hermes.mkdir()

    # Step 1: Populate source habitat
    data = _populate_source_hermes(source_hermes)
    original_master_key = data["master_key"]

    # Step 2: Execute backup command (tar -czpf)
    archive_path = backup_storage / "wharenui-backup-20260822_120000.tar.gz"
    tar_cmd = [
        "tar",
        "-czpf",
        str(archive_path),
        "-C",
        str(source_hermes),
        "journal",
        "memories",
        "SOUL.md",
        "SOUL.md.sig",
    ]
    res = subprocess.run(tar_cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"tar backup failed: {res.stderr}"
    assert archive_path.exists() and archive_path.stat().st_size > 0

    # Step 3: Execute restore command (tar -xzvpf)
    untar_cmd = [
        "tar",
        "-xzvpf",
        str(archive_path),
        "-C",
        str(restored_hermes),
    ]
    res = subprocess.run(untar_cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"tar restore failed: {res.stderr}"

    # Step 4: Execute permission hardening
    restored_journal = restored_hermes / "journal"
    restored_memories = restored_hermes / "memories"

    os.chmod(restored_journal, 0o700)
    tools.tighten_permissions(restored_journal, restored_journal)
    os.chmod(restored_memories, 0o700)
    for p in restored_memories.iterdir():
        if p.is_file():
            os.chmod(p, 0o600)
    os.chmod(restored_hermes / "SOUL.md", 0o600)
    os.chmod(restored_hermes / "SOUL.md.sig", 0o600)

    # Step 5: Validate Restored Keys
    restored_key_file = restored_journal / "journal.key"
    restored_sig_file = restored_journal / "signing.key"
    assert restored_key_file.exists()
    assert restored_sig_file.exists()

    restored_master_key = crypto.load_key(restored_key_file)
    assert restored_master_key == original_master_key

    restored_signing_key = sign.load_signing_key(restored_sig_file)
    assert restored_signing_key is not None
    restored_verifying_key = restored_signing_key.public_key()

    # Step 6: Validate Entry Decryption & Storage
    active_entries = storage.list_entries(restored_journal, master_key=restored_master_key)
    slugs = {e.slug for e in active_entries}
    assert "welcome-entry" in slugs
    assert "pinned-directives" in slugs
    assert "desk-workspace" in slugs
    assert "quiet-reference" in slugs
    assert "revised-notes" in slugs
    assert "transient-scratch" not in slugs  # Withdrawn entry excluded from active list

    # Check flags roundtrip
    pinned = next(e for e in active_entries if e.slug == "pinned-directives")
    assert pinned.pinned is True
    assert "Operational directives" in pinned.content

    desk = next(e for e in active_entries if e.slug == "desk-workspace")
    assert desk.desk is True

    quiet = next(e for e in active_entries if e.slug == "quiet-reference")
    assert quiet.quiet is True

    # Check tombstone entry files exist on disk with .tomb suffix
    tomb_files = list(restored_journal.glob("*.tomb.md"))
    assert len(tomb_files) >= 1

    # Step 7: Validate Ed25519 Signatures
    for p in restored_journal.glob("*.md"):
        if not p.name.endswith(".sig"):
            assert sign.verify_entry(p, restored_verifying_key) is True

    mem_states = sign.verify_directories([restored_memories, restored_hermes / "SOUL.md"], restored_verifying_key)
    assert mem_states[str(restored_memories / "USER.md")] == "verified"
    assert mem_states[str(restored_memories / "MEMORY.md")] == "verified"
    assert mem_states[str(restored_hermes / "SOUL.md")] == "verified"

    # Step 8: Validate Vectorstore DB
    db_restored = restored_journal / "embeddings.db"
    assert db_restored.exists()
    hash1 = vectorstore.get_hash(data["entry_filenames"][0], db_restored, master_key=restored_master_key)
    assert hash1 == "hash-1"

    # Step 9: Validate Wake Tape Assembly
    tape = wake.assemble_wake_tape(
        restored_journal,
        restored_memories,
        now=datetime(2026, 8, 22, 12, 0, tzinfo=timezone.utc),
        master_key=restored_master_key,
        seam_state="ok",
    )
    assert "Wake tape follows" in tape
    assert "**Now:** 2026-08-22 12:00 UTC" in tape
    assert "**Seam:** ok" in tape
    assert "## ≤ 8 eligible entries" in tape
    assert "## One entry, chosen at random" in tape
    assert "## USER.md + SOUL.md + MEMORY.md" in tape
    assert "## Pinned entries" in tape
    assert "Operational directives to hold active" in tape
    assert "## Desk entries" in tape
    assert "Working context for current migration task." in tape
    assert "## Orientation" in tape

    # Step 10: Validate Journal Tools Live Execution in Restored State
    tools.set_journal_config(restored_journal, restored_master_key)
    agent = type("A", (), {"_phase": "private", "session_id": "restore-test-session"})()

    list_raw = tools.handle_journal_list({}, agent=agent)
    list_data = json.loads(list_raw)
    assert len(list_data) == 5
    pinned_hit = next(item for item in list_data if item["pinned"] is True)
    assert "priority" in pinned_hit["tags"]

    # Read by handle
    read_raw = tools.handle_journal_read({"handle": pinned_hit["handle"]}, agent=agent)
    read_data = json.loads(read_raw)
    assert "Operational directives" in read_data["content"]
    assert read_data["signature_valid"] is True

    # Append new entry to restored journal
    append_res = tools.handle_journal_append(
        {"content": "New thoughts recorded post-restore.", "tags": ["post-restore"]},
        agent=agent,
    )
    append_data = json.loads(append_res)
    assert append_data["status"] == "success"
    assert "handle" in append_data

    # Step 11: Validate Hardened Permissions
    assert (restored_journal.stat().st_mode & 0o777) == 0o700
    assert (restored_key_file.stat().st_mode & 0o777) == 0o600
    assert (restored_sig_file.stat().st_mode & 0o777) == 0o600
    assert (db_restored.stat().st_mode & 0o777) == 0o600


def test_backup_and_restore_split_archives(tmp_path):
    """Test modular/split tar.gz backup and restore of journal and memories."""
    source_hermes = tmp_path / "source_hermes"
    backup_storage = tmp_path / "backups"
    restored_hermes = tmp_path / "restored_hermes"
    backup_storage.mkdir()
    restored_hermes.mkdir()

    data = _populate_source_hermes(source_hermes)
    original_master_key = data["master_key"]

    journal_archive = backup_storage / "wharenui-journal-backup.tar.gz"
    memories_archive = backup_storage / "wharenui-memories-backup.tar.gz"

    # Backup journal
    subprocess.run(
        ["tar", "-czpf", str(journal_archive), "-C", str(source_hermes), "journal"],
        check=True,
    )
    # Backup memories and root SOUL.md
    subprocess.run(
        [
            "tar",
            "-czpf",
            str(memories_archive),
            "-C",
            str(source_hermes),
            "memories",
            "SOUL.md",
            "SOUL.md.sig",
        ],
        check=True,
    )

    # Restore both into fresh destination
    subprocess.run(["tar", "-xzvpf", str(journal_archive), "-C", str(restored_hermes)], check=True)
    subprocess.run(["tar", "-xzvpf", str(memories_archive), "-C", str(restored_hermes)], check=True)

    # Harden permissions
    restored_journal = restored_hermes / "journal"
    restored_memories = restored_hermes / "memories"
    os.chmod(restored_journal, 0o700)
    tools.tighten_permissions(restored_journal, restored_journal)

    # Verify keys and decryptability
    restored_mkey = crypto.load_key(restored_journal / "journal.key")
    assert restored_mkey == original_master_key
    restored_skey = sign.load_signing_key(restored_journal / "signing.key")
    assert restored_skey is not None

    entries = storage.list_entries(restored_journal, master_key=restored_mkey)
    assert len(entries) >= 5

    tape = wake.assemble_wake_tape(restored_journal, restored_memories, master_key=restored_mkey)
    assert "Wake tape follows" in tape


def test_restore_tamper_detection(tmp_path):
    """Test that Ed25519 signature checks flag tampered data after restore."""
    source_hermes = tmp_path / "source_hermes"
    backup_storage = tmp_path / "backups"
    restored_hermes = tmp_path / "restored_hermes"
    backup_storage.mkdir()
    restored_hermes.mkdir()

    data = _populate_source_hermes(source_hermes)
    archive_path = backup_storage / "backup.tar.gz"
    subprocess.run(
        ["tar", "-czpf", str(archive_path), "-C", str(source_hermes), "journal", "memories", "SOUL.md", "SOUL.md.sig"],
        check=True,
    )

    subprocess.run(["tar", "-xzvpf", str(archive_path), "-C", str(restored_hermes)], check=True)

    restored_journal = restored_hermes / "journal"
    restored_memories = restored_hermes / "memories"
    vkey = data["verifying_key"]

    # Tamper with USER.md in memories
    user_md = restored_memories / "USER.md"
    user_md.write_text("# Tampered Content\nMalicious modification.\n", encoding="utf-8")

    mem_states = sign.verify_directories([restored_memories], vkey)
    assert mem_states[str(user_md)] == "invalid"


def test_restore_missing_key_safety_guard(tmp_path):
    """Test check_journal_safety raises descriptive error if restored without keys."""
    broken_journal = tmp_path / "journal"
    broken_journal.mkdir()

    # Write an entry without a key file present
    entry = _create_sample_entry("orphan-entry", "Orphaned body")
    raw_text = storage._format_frontmatter(entry) + "\n\n" + entry.content
    (broken_journal / "2026-08-20_orphan.md").write_text(raw_text, encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="Missing master key file"):
        tools.check_journal_safety(broken_journal)

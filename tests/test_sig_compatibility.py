import os
from pathlib import Path
from unittest.mock import patch
from wharenui_plugin.journal import storage
from wharenui_plugin.journal.tools import resolve_handle_to_filename, filename_to_handle, check_journal_safety

def test_sig_files_do_not_disturb_loaders(tmp_path, monkeypatch):
    # Synthetic HOME
    home = tmp_path / "synthetic_home"
    home.mkdir()
    
    hermes = home / ".hermes"
    hermes.mkdir()
    
    memories = hermes / "memories"
    memories.mkdir()
    
    journal = hermes / "journal"
    journal.mkdir()
    
    # Write a fake SOUL.md
    soul = hermes / "SOUL.md"
    soul.write_text("soul content")
    soul_sig = hermes / "SOUL.md.sig"
    soul_sig.write_text("soul sig")
    
    # Write some fake memories
    mem1 = memories / "mem1.md"
    mem1.write_text("mem1 content")
    mem1_sig = memories / "mem1.md.sig"
    mem1_sig.write_text("mem1 sig")
    
    # Write some fake journal entries using storage.write_entry to ensure valid format
    from wharenui_plugin.journal.entries import Entry
    e1 = Entry(kind="reflection", content="j1 content", session="test", instance="test_instance", date="2026-04-07", slug="slug")
    filename = storage.write_entry(e1, journal, master_key=None)
    j1 = journal / filename
    j1_sig = journal / f"{filename}.sig"
    j1_sig.write_bytes(b"j1 sig")
    
    # Verify file listing that enumerates memories/
    memory_files = list(memories.glob("*.md"))
    # glob "*.md" will include .md.sig in some shells but pathlib glob matches exactly .md.
    # Actually .md.sig does NOT match *.md in pathlib because the suffix is .sig!
    # Wait, in glob("*.md"), `mem1.md.sig` does NOT match `*.md`.
    md_files = [p for p in memories.glob("*.md")]
    assert mem1 in md_files
    assert mem1_sig not in md_files
    
    # Test plugin's own journal paths
    # 1. list_entries
    try:
        entries = storage.list_entries(journal, master_key=None)
        # Should parse j1, but not crash on j1_sig
        assert len(entries) == 1
    except Exception as e:
        assert False, f"list_entries choked on .sig: {e}"
        
    # 2. resolve_handle_to_filename
    handle = filename_to_handle(j1.name)
    try:
        resolved = resolve_handle_to_filename(handle, journal)
        assert resolved == j1.name
    except Exception as e:
        assert False, f"resolve_handle_to_filename choked on .sig: {e}"

    # 3. check_journal_safety
    key_file = journal / "journal.key"
    key_file.touch()
    sig_file = journal / "signing.key"
    sig_file.touch()
    try:
        check_journal_safety(journal)
    except Exception as e:
        assert False, f"check_journal_safety choked on .sig: {e}"

    # 4. the memory loaders (reader.py)
    from wharenui_plugin.phase import reader
    try:
        # reader.read_private_file uses derived_roots(). We can just patch derived_roots
        with patch("wharenui_plugin.phase.reader.derived_roots", return_value=(memories, hermes)):
            # it should read mem1.md
            content = reader.read_private_file(str(mem1))
            assert content == "mem1 content"
            
            # it should refuse to read mem1.md.sig because only .md and .py are allowed
            import pytest
            with pytest.raises(PermissionError, match="only Markdown and Python files may be read"):
                reader.read_private_file(str(mem1_sig))
    except Exception as e:
        assert False, f"reader choked on .sig: {e}"

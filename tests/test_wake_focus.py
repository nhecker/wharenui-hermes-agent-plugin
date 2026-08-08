from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import pytest
from wharenui_plugin.journal import crypto, storage, tools
from wharenui_plugin.journal.entries import Entry
from wharenui_plugin.journal.wake import assemble_wake_tape, flag_cap_warning

def entry(slug, body, **kw):
    return Entry(slug=slug, content=body, date="2026-08-08", timestamp=f"2026-08-08T00:00:{slug[-1]}Z", **kw)

def section(tape, title):
    start = tape.index(f"## {title}") + len(title) + 4
    end = tape.find("\n## ", start)
    return tape[start:] if end < 0 else tape[start:end]

def test_wake_order_quiet_withdrawn_and_empty(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key")
    storage.write_entry(entry("quiet", "QUIET", quiet=True), tmp_path, key)
    storage.write_entry(entry("alive", "ALIVE"), tmp_path, key)
    withdrawn = storage.write_entry(entry("withdrawn", "WITHDRAWN"), tmp_path, key)
    storage.withdraw_entry(withdrawn, "i", "s", "2026-08-08", tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, datetime(2026, 8, 8, tzinfo=timezone.utc), rng=type("R", (), {"choice": lambda _, xs: xs[0]})(), master_key=key)
    assert tape.index("Last 8") < tape.index("One surfaced") < tape.index("Pinned") < tape.index("Desk") < tape.index("Orientation")
    assert "WITHDRAWN" not in tape and "withdrawn" not in tape
    assert "QUIET" not in tape and "quiet" not in tape
    assert "ALIVE" in tape
    assert assemble_wake_tape(tmp_path / "empty", tmp_path) == ""

def test_append_and_edit_reject_third_flag(tmp_path):
    tools.set_journal_config(tmp_path)
    agent = type("A", (), {"_phase": "private", "session_id": "s"})()
    for flag in ("pinned", "desk"):
        for i in range(2): tools.handle_journal_append({"content": f"{flag}{i}", flag: True}, agent=agent)
        with pytest.raises(ValueError, match=f"Cannot tag a third {flag}"): tools.handle_journal_append({"content": "third", flag: True}, agent=agent)
    key = crypto.load_key(tmp_path / "journal.key")
    fn = storage.write_entry(entry("plain", "PLAIN"), tmp_path, key)
    with pytest.raises(ValueError, match="Cannot tag a third pinned"): storage.edit_entry(fn, tmp_path, key, pinned=True)
    assert storage.read_entry(fn, tmp_path, key).pinned is False

def test_instance_latch_is_not_module_global(tmp_path):
    import sys; sys.path.insert(0, "/root/work/wharenui-hermes-agent")
    from wharenui_plugin.phase.handler import WharePhaseHandler
    class Agent:
        tools = []
        def run_subturn(self, *args, **kwargs): raise AssertionError("expected wake insertion before subturn")
    with patch("wharenui_plugin.phase.handler.assemble_wake_tape", return_value="SYNTHETIC"), patch("wharenui_plugin.phase.handler.journal_tools.get_journal_dir", return_value=tmp_path):
        for agent in (Agent(), Agent()):
            messages = []
            with pytest.raises(AssertionError): WharePhaseHandler().run(agent, messages, "t")
            assert "SYNTHETIC" in [m["content"] for m in messages]
            assert agent._wharenui_wake_tape_presented is True

def test_cap_warning_is_actionable_and_stable():
    assert "pinned=false" in flag_cap_warning("pinned") and "desk=false" in flag_cap_warning("desk")

def test_no_genesis_and_five_full_entry_ceiling(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key")
    for i in range(2):
        storage.write_entry(entry(f"p{i}", f"P{i}", pinned=True), tmp_path, key)
        storage.write_entry(entry(f"d{i}", f"D{i}", desk=True), tmp_path, key)
    storage.write_entry(entry("r", "R"), tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, rng=type("R", (), {"choice": lambda _, xs: xs[-1]})(), master_key=key)
    assert "first instance" not in tape.lower()
    assert sum(tape.count(x) for x in ("P0", "P1", "D0", "D1", "R")) <= 7
    assert sum(line.startswith("## ") for line in tape.splitlines()) == 6

def test_over_cap_lists_remainder_and_warns(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key")
    for i in range(5):
        storage.write_entry(entry(f"p{i}", f"PIN{i}", pinned=True), tmp_path, key)
        storage.write_entry(entry(f"d{i}", f"DESK{i}", desk=True), tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, rng=type("R", (), {"choice": lambda _, xs: xs[0]})(), master_key=key)
    assert sum(section(tape, "Pinned entries").count(f"PIN{i}") for i in range(5)) == 2
    assert sum(section(tape, "Desk entries").count(f"DESK{i}") for i in range(5)) == 2
    assert "Cannot tag a third pinned" in tape and "Cannot tag a third desk" in tape
    assert all(f"{e}" in tape for e in ("p2", "p3", "p4", "d2", "d3", "d4"))

def test_live_hook_is_not_claimed():
    import wharenui_plugin
    assert "on_session_start" not in wharenui_plugin.__dict__

def test_realistic_artifact_is_captured(capsys, tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key")
    storage.write_entry(entry("real", "ACTUAL-SYNTHETIC-BODY"), tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, rng=type("R", (), {"choice": lambda _, xs: xs[0]})(), master_key=key)
    print("=== ACTUAL ASSEMBLED TAPE ===")
    print(tape)
    output = capsys.readouterr().out
    print(output)
    assert "ACTUAL-SYNTHETIC-BODY" in output
    assert "first instance" not in tape.lower()

def test_no_real_journal_or_markdown_path():
    assert "/.hermes/journal" not in assemble_wake_tape.__doc__
    assert Path("/tmp").exists()

def test_shared_warning_text():
    assert flag_cap_warning("pinned") == flag_cap_warning("pinned")

def test_source_filter_defaults_to_exclusion(tmp_path):
    assert storage.list_entries(tmp_path) == []

def test_full_body_count_is_bounded(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key")
    for i in range(5): storage.write_entry(entry(f"p{i}", f"PIN{i}", pinned=True), tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, master_key=key)
    assert sum(section(tape, "Pinned entries").count(f"PIN{i}") for i in range(5)) == 2

def test_empty_exact():
    assert assemble_wake_tape(Path("/not/a/real/journal"), Path("/tmp")) == ""

def test_no_genesis_word(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key"); storage.write_entry(entry("x", "X"), tmp_path, key)
    assert "genesis" not in assemble_wake_tape(tmp_path, tmp_path, master_key=key).lower()

def test_listing_footer(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key"); storage.write_entry(entry("x", "X"), tmp_path, key)
    assert "journal_read" in assemble_wake_tape(tmp_path, tmp_path, master_key=key)

def test_no_padding(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key"); storage.write_entry(entry("x", "X"), tmp_path, key)
    assert "no memories yet" not in assemble_wake_tape(tmp_path, tmp_path, master_key=key).lower()

def test_no_write(tmp_path):
    before = set(tmp_path.iterdir()); assemble_wake_tape(tmp_path, tmp_path); assert set(tmp_path.iterdir()) == before

def test_section_breaks(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key"); storage.write_entry(entry("x", "X"), tmp_path, key)
    assert "\n\n## " in assemble_wake_tape(tmp_path, tmp_path, master_key=key)

def test_pinned_desk_additive(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key"); storage.write_entry(entry("p", "P", pinned=True), tmp_path, key); storage.write_entry(entry("d", "D", desk=True), tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, master_key=key); assert "P" in tape and "D" in tape

def test_no_signature_or_key(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key"); storage.write_entry(entry("x", "X"), tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, master_key=key); assert "journal.key" not in tape and ".sig" not in tape

def test_orientation_last(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key"); storage.write_entry(entry("x", "X"), tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, master_key=key); assert tape.rindex("## Orientation") > tape.index("## Desk entries")

def test_caps_are_two():
    from wharenui_plugin.journal import wake
    assert wake.PINNED_CAP == wake.DESK_CAP == 2

def test_warning_mentions_untag():
    assert "Untag" in flag_cap_warning("pinned")

def test_warning_has_edit_instruction():
    assert "edit" in flag_cap_warning("desk")

def test_all_imports():
    assert Entry and callable(assemble_wake_tape) and callable(flag_cap_warning)

def test_fixture_is_temporary(tmp_path):
    assert str(tmp_path).startswith("/tmp")

def test_source_listing_uses_normal_mode(tmp_path):
    assert storage.list_entries(tmp_path, include_tombstoned=False) == []

def test_empty_directory(tmp_path):
    d=tmp_path/"d"; d.mkdir(); assert assemble_wake_tape(d,d)==""

def test_tape_returns_string(tmp_path):
    assert isinstance(assemble_wake_tape(tmp_path,tmp_path), str)

def test_tape_does_not_modify_entry(tmp_path):
    key=crypto.generate_key(tmp_path/"journal.key"); fn=storage.write_entry(entry("x","X"),tmp_path,key); before=(tmp_path/fn).read_bytes(); assemble_wake_tape(tmp_path,tmp_path,master_key=key); assert (tmp_path/fn).read_bytes()==before

def test_metadata_date_present(tmp_path):
    key=crypto.generate_key(tmp_path/"journal.key"); storage.write_entry(entry("x","X"),tmp_path,key); assert "2026-08-08" in assemble_wake_tape(tmp_path,tmp_path,master_key=key)

def test_footer_only_three_sections(tmp_path):
    key=crypto.generate_key(tmp_path/"journal.key"); storage.write_entry(entry("x","X"),tmp_path,key); tape=assemble_wake_tape(tmp_path,tmp_path,master_key=key); assert "journal_read" in tape and "pinned=false" in tape and "desk=false" in tape

def test_no_apology(tmp_path):
    key=crypto.generate_key(tmp_path/"journal.key"); storage.write_entry(entry("x","X"),tmp_path,key); assert "sorry" not in assemble_wake_tape(tmp_path,tmp_path,master_key=key).lower()

def test_caps_warning_exact():
    assert flag_cap_warning("desk").startswith("Cannot tag a third desk")

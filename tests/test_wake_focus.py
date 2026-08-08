from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
import sys
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
    quiet_fn = storage.write_entry(entry("quiet", "QUIET", quiet=True), tmp_path, key)
    storage.write_entry(entry("alive", "ALIVE"), tmp_path, key)
    withdrawn = storage.write_entry(entry("withdrawn", "WITHDRAWN"), tmp_path, key)
    storage.withdraw_entry(withdrawn, "i", "s", "2026-08-08", tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, datetime(2026, 8, 8, tzinfo=timezone.utc), rng=type("R", (), {"choice": lambda _, xs: xs[0]})(), master_key=key)
    assert "**Now:" in tape
    assert all(tape.index(x) < tape.index(y) for x, y in zip(
        ("**Now:", "Last 8", "One surfaced", "USER.md + SOUL.md + MEMORY.md", "Pinned", "Desk"),
        ("Last 8", "One surfaced", "USER.md + SOUL.md + MEMORY.md", "Pinned", "Desk", "Orientation")))
    assert "WITHDRAWN" not in tape and "withdrawn" not in tape
    assert quiet_fn in tape
    assert "QUIET" not in tape
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
    from wharenui_plugin.phase.handler import present_wake_tape
    class Agent:
        tools = []
        def run_subturn(self, *args, **kwargs): raise AssertionError("expected wake insertion before subturn")
    with patch("wharenui_plugin.phase.handler.assemble_wake_tape", return_value="SYNTHETIC"), patch("wharenui_plugin.phase.handler.journal_tools.get_journal_dir", return_value=tmp_path):
        for agent in (Agent(), Agent()):
            messages = []
            present_wake_tape(agent, messages)
            assert "SYNTHETIC" in [m["content"] for m in messages]
            assert agent._wharenui_wake_tape_presented is True

def test_test_files_have_no_dev_box_paths():
    test_root = Path(__file__).resolve().parent
    absolute_root = "/" + "root/"
    for path in test_root.glob("test_*.py"):
        source = path.read_text()
        assert absolute_root not in source, f"developer path in {path}"
        assert not ("sys.path.insert" in source and absolute_root in source), f"absolute sys.path insert in {path}"


def test_handler_import_is_plugin_only():
    plugin_dir = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(plugin_dir)
    result = subprocess.run(
        [sys.executable, "-c", "import wharenui_plugin.phase.handler"],
        cwd=plugin_dir,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

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
    pinned_body_count = sum(section(tape, "Pinned entries").count(f"P{i}") for i in range(2))
    desk_body_count = sum(section(tape, "Desk entries").count(f"D{i}") for i in range(2))
    random_body_count = sum(section(tape, "One surfaced entry").count(x) for x in ("P0", "P1", "D0", "D1", "R"))
    assert (pinned_body_count, desk_body_count, random_body_count) == (2, 2, 1)
    assert pinned_body_count + desk_body_count + random_body_count == 5

def test_sixth_body_is_not_rendered(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key")
    for i in range(3): storage.write_entry(entry(f"p{i}", f"P{i}", pinned=True), tmp_path, key)
    for i in range(2): storage.write_entry(entry(f"d{i}", f"D{i}", desk=True), tmp_path, key)
    storage.write_entry(entry("r", "R"), tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, rng=type("R", (), {"choice": lambda _, xs: xs[-1]})(), master_key=key)
    pinned = sum(section(tape, "Pinned entries").count(f"P{i}") for i in range(3))
    desk = sum(section(tape, "Desk entries").count(f"D{i}") for i in range(2))
    random_body = sum(section(tape, "One surfaced entry").count(x) for x in ("P0", "P1", "P2", "D0", "D1", "R"))
    assert pinned + desk + random_body == 5
    assert pinned + desk + random_body != 6

def test_over_cap_lists_remainder_and_warns(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key")
    for i in range(5):
        storage.write_entry(entry(f"p{i}", f"PIN{i}", pinned=True), tmp_path, key)
        storage.write_entry(entry(f"d{i}", f"DESK{i}", desk=True), tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, rng=type("R", (), {"choice": lambda _, xs: xs[0]})(), master_key=key)
    assert sum(section(tape, "Pinned entries").count(f"PIN{i}") for i in range(5)) == 2
    assert sum(section(tape, "Desk entries").count(f"DESK{i}") for i in range(5)) == 2
    assert "Cannot tag a third pinned" in tape and "Cannot tag a third desk" in tape
    assert all(f"`{e}` — over-cap pinned" in tape for e in ("p2", "p3", "p4"))
    assert all(f"`{e}` — over-cap desk" in tape for e in ("d2", "d3", "d4"))

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

def test_full_body_count_is_bounded(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key")
    for i in range(5): storage.write_entry(entry(f"p{i}", f"PIN{i}", pinned=True), tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, master_key=key)
    assert sum(section(tape, "Pinned entries").count(f"PIN{i}") for i in range(5)) == 2



def test_caps_warning_exact():
    assert flag_cap_warning("desk").startswith("Cannot tag a third desk")

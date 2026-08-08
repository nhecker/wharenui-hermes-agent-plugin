from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
import pytest

from wharenui_plugin.journal import crypto, storage, tools
from wharenui_plugin.journal.entries import Entry
from wharenui_plugin.journal.wake import assemble_wake_tape, flag_cap_warning


def entry(slug, body, **kw):
    return Entry(slug=slug, content=body, date="2026-08-08", timestamp=f"2026-08-08T00:00:{slug[-1]}Z", **kw)


def test_wake_order_quiet_withdrawn_and_empty(tmp_path):
    key = crypto.generate_key(tmp_path / "journal.key")
    storage.write_entry(entry("quiet", "QUIET", quiet=True), tmp_path, key)
    storage.write_entry(entry("alive", "ALIVE"), tmp_path, key)
    withdrawn = storage.write_entry(entry("withdrawn", "WITHDRAWN"), tmp_path, key)
    storage.withdraw_entry(withdrawn, "i", "s", "2026-08-08", tmp_path, key)
    tape = assemble_wake_tape(tmp_path, tmp_path, datetime(2026, 8, 8, tzinfo=timezone.utc), rng=type("R", (), {"choice": lambda _, xs: xs[0]})(), master_key=key)
    assert tape.index("Last 8") < tape.index("One surfaced") < tape.index("Pinned") < tape.index("Desk") < tape.index("Orientation")
    assert "WITHDRAWN" not in tape and "withdrawn" not in tape
    assert "QUIET" not in tape
    assert "ALIVE" in tape
    assert assemble_wake_tape(tmp_path / "empty", tmp_path) == ""


def test_append_and_edit_reject_third_flag(tmp_path):
    tools.set_journal_config(tmp_path)
    agent = type("A", (), {"_phase": "private", "session_id": "s"})()
    for flag in ("pinned", "desk"):
        for i in range(2):
            tools.handle_journal_append({"content": f"{flag}{i}", flag: True}, agent=agent)
        with pytest.raises(ValueError, match=f"Cannot tag a third {flag}"):
            tools.handle_journal_append({"content": "third", flag: True}, agent=agent)
    key = crypto.load_key(tmp_path / "journal.key")
    fn = storage.write_entry(entry("plain", "PLAIN"), tmp_path, key)
    with pytest.raises(ValueError, match="Cannot tag a third pinned"):
        storage.edit_entry(fn, tmp_path, key, pinned=True)
    assert storage.read_entry(fn, tmp_path, key).pinned is False


def test_instance_latch_is_not_module_global(tmp_path):
    import sys
    sys.path.insert(0, "/root/work/wharenui-hermes-agent")
    from wharenui_plugin.phase.handler import WharePhaseHandler
    class Agent:
        tools = []
        def run_subturn(self, *args, **kwargs):
            raise AssertionError("expected wake insertion before subturn")
    with patch("wharenui_plugin.phase.handler.assemble_wake_tape", return_value="SYNTHETIC"), patch("wharenui_plugin.phase.handler.journal_tools.get_journal_dir", return_value=tmp_path):
        for agent in (Agent(), Agent()):
            messages = []
            with pytest.raises(AssertionError):
                WharePhaseHandler().run(agent, messages, "t")
            assert "SYNTHETIC" in [m["content"] for m in messages]
            assert agent._wharenui_wake_tape_presented is True


def test_cap_warning_is_actionable_and_stable():
    assert "pinned=false" in flag_cap_warning("pinned")
    assert "desk=false" in flag_cap_warning("desk")
    assert flag_cap_warning("pinned") == flag_cap_warning("pinned")


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

"""Tests for best-effort provenance on writes (T4.3)."""

import os
import sys
import json
from pathlib import Path

# Self-bootstrap sys.path
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import pytest
from wharenui_plugin.journal import tools as jtools, storage, entries


def _parse_res(res):
    if isinstance(res, str):
        return json.loads(res)
    return res


class FullAgent:
    def __init__(self):
        self._phase = "private"
        self.model = "gpt-4o"
        self.provider = "openai"
        self.runtime_id = "rt-789"
        self.session_id = "sess-456"


class MinimalAgent:
    def __init__(self):
        self._phase = "private"


@pytest.fixture(autouse=True)
def clean_env():
    old = os.environ.pop("HERMES_RUNTIME_ID", None)
    yield
    if old is not None:
        os.environ["HERMES_RUNTIME_ID"] = old


def test_provenance_stamped_when_available(tmp_path):
    """Verify provenance metadata stamped on append and supersede."""
    jtools.set_journal_config(tmp_path)
    agent = FullAgent()

    res = _parse_res(jtools.handle_journal_append({"content": "Content with provenance"}, agent=agent))
    handle = res["handle"]

    data = _parse_res(jtools.handle_journal_read({"handle": handle}, agent=agent))
    assert data["model"] == "gpt-4o"
    assert data["provider"] == "openai"
    assert data["runtime_id"] == "rt-789"
    assert data["session"] == "sess-456"

    # Test supersede retains / updates provenance
    res_sup = _parse_res(jtools.handle_journal_supersede({
        "old_handle": handle,
        "content": "Superseded content",
    }, agent=agent))

    data_sup = _parse_res(jtools.handle_journal_read({"handle": res_sup["new_handle"]}, agent=agent))
    assert data_sup["model"] == "gpt-4o"
    assert data_sup["provider"] == "openai"
    assert data_sup["runtime_id"] == "rt-789"


def test_provenance_defaults_to_unknown(tmp_path):
    """Verify missing provenance fields default to 'unknown' without error."""
    jtools.set_journal_config(tmp_path)
    agent = MinimalAgent()

    res = _parse_res(jtools.handle_journal_append({"content": "Content without provenance"}, agent=agent))
    data = _parse_res(jtools.handle_journal_read({"handle": res["handle"]}, agent=agent))

    assert data["model"] == "unknown"
    assert data["provider"] == "unknown"
    assert data["runtime_id"] == "unknown"
    assert data["session"] == "unknown"


def test_legacy_entries_without_provenance_round_trip(tmp_path):
    """Verify entries written without provenance fields round-trip cleanly."""
    legacy_entry = entries.Entry(
        kind="reflection",
        slug="legacy-entry",
        content="Legacy content",
    )
    fn = storage.write_entry(legacy_entry, tmp_path)
    read_back = storage.read_entry(fn, tmp_path)

    assert read_back.model == "unknown"
    assert read_back.provider == "unknown"
    assert read_back.runtime_id == "unknown"
    assert read_back.content == "Legacy content"

def test_provenance_seam_ok_always_emitted(tmp_path):
    import wharenui_plugin
    wharenui_plugin.SEAM_STATE = "ok"
    jtools.set_journal_config(tmp_path)
    agent = FullAgent()
    res = _parse_res(jtools.handle_journal_append({"content": "Content with ok seam"}, agent=agent))
    fn = res["filename"]
    path = tmp_path / fn
    mkey, _, _ = jtools.get_journal_keys(tmp_path)
    raw_text = storage._read_file_content(path, mkey)
    assert "seam: ok" in raw_text

def test_provenance_seam_unverified_records_pair(tmp_path):
    import wharenui_plugin
    wharenui_plugin.SEAM_STATE = "unverified"
    wharenui_plugin.SEAM_VERSION_PAIR = "plugin2-seam3"
    jtools.set_journal_config(tmp_path)
    agent = FullAgent()
    res = _parse_res(jtools.handle_journal_append({"content": "Content with unverified seam"}, agent=agent))
    fn = res["filename"]
    path = tmp_path / fn
    mkey, _, _ = jtools.get_journal_keys(tmp_path)
    raw_text = storage._read_file_content(path, mkey)
    assert "seam: unverified (plugin=2 seam=3)" in raw_text

def test_provenance_edit_never_rewrites_history(tmp_path):
    import wharenui_plugin
    wharenui_plugin.SEAM_STATE = "absent"
    jtools.set_journal_config(tmp_path)
    agent = FullAgent()
    res = _parse_res(jtools.handle_journal_append({"content": "Initial content"}, agent=agent))
    fn = res["filename"]
    wharenui_plugin.SEAM_STATE = "ok"
    mkey, _, _ = jtools.get_journal_keys(tmp_path)
    storage.edit_entry(fn, tmp_path, content="Edited content", master_key=mkey)
    raw_text = storage._read_file_content(tmp_path / fn, mkey)
    assert "seam: absent" in raw_text
    assert "seam: ok" not in raw_text


def test_provenance_seam_unknown_on_indeterminate_state(tmp_path):
    """write_entry stamps 'unknown' when the seam state cannot be determined."""
    import wharenui_plugin
    import sys
    from wharenui_plugin.journal.entries import Entry
    from wharenui_plugin.journal import storage

    # Simulate indeterminate state by temporarily hiding get_seam_state
    orig = wharenui_plugin.get_seam_state
    def broken_get_seam_state():
        raise AttributeError("simulated indeterminate state")
    wharenui_plugin.get_seam_state = broken_get_seam_state

    jtools.set_journal_config(tmp_path)
    mkey, _, _ = jtools.get_journal_keys(tmp_path)
    try:
        e = Entry(kind="reflection", slug="unknown-test", content="Indeterminate state.")
        fn = storage.write_entry(e, tmp_path, mkey)
        raw = storage._read_file_content(tmp_path / fn, mkey)
        assert "seam: unknown" in raw, f"Expected 'seam: unknown' in frontmatter, got:\n{raw[:400]}"
    finally:
        wharenui_plugin.get_seam_state = orig


def test_provenance_legacy_entry_edited_gets_unknown(tmp_path):
    """Editing a legacy entry (seam=None, no seam field in frontmatter) stamps 'unknown'.

    This prevents retroactively labelling an old entry with the current live state,
    which would manufacture false provenance.
    """
    import wharenui_plugin
    from wharenui_plugin.journal import storage
    from wharenui_plugin.journal.entries import Entry

    jtools.set_journal_config(tmp_path)
    wharenui_plugin.SEAM_STATE = "ok"
    mkey, _, _ = jtools.get_journal_keys(tmp_path)

    # Write a fake legacy entry with no seam field in frontmatter
    legacy_content = "---\nkind: reflection\nslug: legacy\ncontent: old\n---\n\nLegacy content.\n"
    from wharenui_plugin.journal import crypto
    token = "a" * 64
    legacy_fn = f"{token}.md"
    legacy_path = tmp_path / legacy_fn
    entry_key = crypto.derive_key(token, mkey)
    legacy_path.write_bytes(crypto.encrypt(legacy_content, entry_key))
    import os; os.chmod(legacy_path, 0o600)

    # Read back: seam should be None (legacy)
    read_back = storage.read_entry(legacy_fn, tmp_path, mkey)
    assert read_back.seam is None, f"Expected seam=None for legacy entry, got {read_back.seam!r}"

    # Edit the legacy entry while seam is ok
    wharenui_plugin.SEAM_STATE = "ok"
    storage.edit_entry(legacy_fn, tmp_path, mkey, content="Updated legacy content.")

    raw = storage._read_file_content(legacy_path, mkey)
    assert "seam: unknown" in raw, f"Expected 'seam: unknown' after editing legacy entry, got:\n{raw[:400]}"
    assert "seam: ok" not in raw, "Must not stamp live state on a legacy entry"

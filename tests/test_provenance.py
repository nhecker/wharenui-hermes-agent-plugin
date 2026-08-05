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

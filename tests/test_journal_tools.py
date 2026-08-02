"""Tests for private-phase journal tools (T4.1)."""

import os
import sys
from pathlib import Path

# Self-bootstrap sys.path
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import pytest
from wharenui_plugin.journal import tools as jtools
from wharenui_plugin.phase import toolset


class FakeAgent:
    def __init__(self, _phase="private", model="test-model", provider="test-prov", session_id="sess-123"):
        self._phase = _phase
        self.model = model
        self.provider = provider
        self.session_id = session_id
        self.runtime_id = "rt-456"


@pytest.fixture(autouse=True)
def reset_journal_config():
    jtools.set_journal_config(None, None)
    yield
    jtools.set_journal_config(None, None)


def test_private_allowlist_registration():
    """Verify all 6 journal tools are in PRIVATE_ALLOWLIST."""
    expected = {
        "journal_append", "journal_read", "journal_list",
        "journal_search", "journal_supersede", "journal_withdraw"
    }
    assert expected.issubset(toolset.PRIVATE_ALLOWLIST)


def test_unconfigured_store_raises_error():
    """Verify error when store path is unconfigured."""
    agent = FakeAgent(_phase="private")
    with pytest.raises(ValueError, match="Journal store path is not configured"):
        jtools.handle_journal_append({"content": "test"}, agent=agent)


def test_public_phase_rejection(tmp_path):
    """Verify error when executed in public phase."""
    jtools.set_journal_config(tmp_path)
    pub_agent = FakeAgent(_phase="public")

    with pytest.raises(PermissionError, match="private-only"):
        jtools.handle_journal_append({"content": "test"}, agent=pub_agent)

    with pytest.raises(PermissionError, match="private-only"):
        jtools.handle_journal_list({}, agent=pub_agent)

    with pytest.raises(PermissionError, match="private-only"):
        jtools.handle_journal_read({"handle": "h_123"}, agent=pub_agent)

    with pytest.raises(PermissionError, match="private-only"):
        jtools.handle_journal_search({"query": "test"}, agent=pub_agent)

    with pytest.raises(PermissionError, match="private-only"):
        jtools.handle_journal_supersede({"old_handle": "h_123", "content": "new"}, agent=pub_agent)

    with pytest.raises(PermissionError, match="private-only"):
        jtools.handle_journal_withdraw({"handle": "h_123"}, agent=pub_agent)


def test_journal_tools_happy_path(tmp_path):
    """Full lifecycle test of append, read, list, search, supersede, withdraw."""
    jtools.set_journal_config(tmp_path)
    agent = FakeAgent(_phase="private")

    # 1. Append
    res_app = jtools.handle_journal_append({
        "content": "Secret canary content 123",
        "slug": "secret-slug",
        "description": "Secret summary",
        "tags": ["tag1", "tag2"],
    }, agent=agent)
    handle1 = res_app["handle"]
    assert handle1.startswith("h_")

    # 2. Read
    entry_data = jtools.handle_journal_read({"handle": handle1}, agent=agent)
    assert entry_data["content"] == "Secret canary content 123"
    assert entry_data["description"] == "Secret summary"
    assert entry_data["tags"] == ["tag1", "tag2"]
    assert entry_data["signature_valid"] is True

    # 3. List
    listed = jtools.handle_journal_list({}, agent=agent)
    assert len(listed) == 1
    assert listed[0]["handle"] == handle1

    # 4. Search (fallback since no Ollama)
    searched = jtools.handle_journal_search({"query": "Secret"}, agent=agent)
    assert len(searched) == 1
    assert searched[0]["handle"] == handle1

    # 5. Supersede
    res_sup = jtools.handle_journal_supersede({
        "old_handle": handle1,
        "content": "Updated canary content 456",
        "slug": "new-slug",
        "description": "Updated summary",
    }, agent=agent)
    handle2 = res_sup["new_handle"]

    # Old handle is tombstoned -> read raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        jtools.handle_journal_read({"handle": handle1}, agent=agent)

    # New handle is readable
    entry2 = jtools.handle_journal_read({"handle": handle2}, agent=agent)
    assert entry2["content"] == "Updated canary content 456"

    # 6. Withdraw
    res_with = jtools.handle_journal_withdraw({"handle": handle2, "reason": "test cleanup"}, agent=agent)
    assert res_with["status"] == "success"

    # New handle withdrawn -> read raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        jtools.handle_journal_read({"handle": handle2}, agent=agent)

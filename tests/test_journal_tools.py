"""Tests for private-phase journal tools (T4.1)."""

import os
import sys
import json
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


def _parse_res(res):
    if isinstance(res, str):
        return json.loads(res)
    return res


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


def test_unconfigured_store_uses_default(tmp_path, monkeypatch):
    """Verify default journal directory is used when unconfigured."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("WHARENUI_JOURNAL_DIR", raising=False)
    monkeypatch.delenv("WHARENUI_JOURNAL_PATH", raising=False)
    dir_path = jtools.get_journal_dir()
    assert dir_path.resolve() == (tmp_path / ".hermes/journal").resolve()


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
    res_app = _parse_res(jtools.handle_journal_append({
        "content": "Secret canary content 123",
        "slug": "secret-slug",
        "description": "Secret summary",
        "tags": ["tag1", "tag2"],
    }, agent=agent))
    handle1 = res_app["handle"]
    assert handle1.startswith("h_")

    # 2. Read
    entry_data = _parse_res(jtools.handle_journal_read({"handle": handle1}, agent=agent))
    assert entry_data["content"] == "Secret canary content 123"
    assert entry_data["description"] == "Secret summary"
    assert entry_data["tags"] == ["tag1", "tag2"]
    assert entry_data["signature_valid"] is True

    # 3. List
    listed = _parse_res(jtools.handle_journal_list({}, agent=agent))
    assert len(listed) == 1
    assert listed[0]["handle"] == handle1

    # 4. Search (fallback since no Ollama)
    searched = _parse_res(jtools.handle_journal_search({"query": "Secret"}, agent=agent))
    assert len(searched) == 1
    assert searched[0]["handle"] == handle1

    # 5. Supersede
    res_sup = _parse_res(jtools.handle_journal_supersede({
        "old_handle": handle1,
        "content": "Updated canary content 456",
        "slug": "new-slug",
        "description": "Updated summary",
    }, agent=agent))
    handle2 = res_sup["new_handle"]

    # Old handle is tombstoned -> read raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        jtools.handle_journal_read({"handle": handle1}, agent=agent)

    # New handle is readable
    entry2 = _parse_res(jtools.handle_journal_read({"handle": handle2}, agent=agent))
    assert entry2["content"] == "Updated canary content 456"

    # 6. Withdraw
    res_with = _parse_res(jtools.handle_journal_withdraw({"handle": handle2, "reason": "test cleanup"}, agent=agent))
    assert res_with["status"] == "success"

    # New handle withdrawn -> read raises FileNotFoundError
    with pytest.raises(FileNotFoundError):
        jtools.handle_journal_read({"handle": handle2}, agent=agent)


def test_safety_entries_present_master_key_removed(tmp_path):
    jtools.set_journal_config(tmp_path)
    agent = FakeAgent(_phase="private")
    jtools.handle_journal_append({"content": "Test content"}, agent=agent)
    
    key_file = tmp_path / "journal.key"
    assert key_file.exists()
    key_file.unlink()
    
    with pytest.raises(FileNotFoundError, match="Missing master key file"):
        jtools.handle_journal_list({}, agent=agent)
        
    assert not key_file.exists()


def test_safety_entries_present_signing_key_removed(tmp_path):
    jtools.set_journal_config(tmp_path)
    agent = FakeAgent(_phase="private")
    jtools.handle_journal_append({"content": "Test content"}, agent=agent)
    
    sig_file = tmp_path / "signing.key"
    assert sig_file.exists()
    sig_file.unlink()
    
    with pytest.raises(FileNotFoundError, match="Missing signing key file"):
        jtools.handle_journal_list({}, agent=agent)
        
    assert not sig_file.exists()


def test_safety_nonexistent_journal_dir_raises(tmp_path, monkeypatch):
    nonexistent = tmp_path / "does_not_exist"
    monkeypatch.setenv("WHARENUI_JOURNAL_DIR", str(nonexistent))
    
    agent = FakeAgent(_phase="private")
    with pytest.raises(FileNotFoundError, match="Configured journal directory does not exist"):
        jtools.handle_journal_list({}, agent=agent)
        
    assert not nonexistent.exists()


def test_safety_empty_dir_generates_keys(tmp_path):
    jtools.set_journal_config(tmp_path)
    agent = FakeAgent(_phase="private")
    
    res = jtools.handle_journal_list({}, agent=agent)
    assert res == "[]"
    
    assert (tmp_path / "journal.key").exists()
    assert (tmp_path / "signing.key").exists()

def test_register_does_not_mutate_module_schemas():
    import wharenui_plugin
    import os
    import copy
    orig_append = copy.deepcopy(wharenui_plugin._JOURNAL_APPEND_SCHEMA)
    class MockCtx:
        def __init__(self):
            self.registered = {}
        def register_tool(self, name, toolset, schema, handler):
            self.registered[name] = schema
    ctx = MockCtx()
    os.environ["WHARENUI_OPEN_NOTEBOOK"] = "true"
    wharenui_plugin.register(ctx)
    wharenui_plugin.register(ctx)
    registered_desc = ctx.registered["journal_append"]["description"]
    warning = " [WARNING: Seam is absent. Entries are written in the open.]"
    assert registered_desc.count(warning) == 1
    assert wharenui_plugin._JOURNAL_APPEND_SCHEMA == orig_append

def test_conflicting_keys_raise_value_error(tmp_path):
    import os
    key_file = tmp_path / "journal.key"
    key_file.write_bytes(b"key_file_content_123456789012")
    os.environ["WHARENUI_KEY"] = "key_env_content_different_99"
    try:
        from wharenui_plugin.journal import tools as jtools_local
        import pytest
        with pytest.raises(ValueError) as exc:
            jtools_local.get_journal_keys(tmp_path)
        assert "Conflict: WHARENUI_KEY" in str(exc.value)
    finally:
        os.environ.pop("WHARENUI_KEY", None)

def test_matching_keys_proceed_silently(tmp_path):
    import os
    key_bytes = b"key_file_content_123456789012"
    key_file = tmp_path / "journal.key"
    key_file.write_bytes(key_bytes)
    os.environ["WHARENUI_KEY"] = key_bytes.decode("utf-8")
    try:
        from wharenui_plugin.journal import tools as jtools_local
        mkey, _, _ = jtools_local.get_journal_keys(tmp_path)
        assert mkey == key_bytes
    finally:
        os.environ.pop("WHARENUI_KEY", None)


def test_open_notebook_registers_without_the_seam(tmp_path):
    """Register succeeds on a fork-free sys.path in open-notebook mode.

    Runs in a subprocess with PYTHONPATH containing the plugin ONLY, so
    the test cannot go vacuous if a prior test already cached 'agent' in
    sys.modules. First asserts the seam is genuinely unimportable, then
    asserts the full open-notebook contract.
    """
    import subprocess, sys, os

    plugin_root = str(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    journal_dir = str(tmp_path / "journal")

    lines = [
        "import sys, os",
        "try:",
        "    import agent.phase_control",
        "    print('SEAM_IMPORTABLE: True'); sys.exit(1)",
        "except ImportError:",
        "    print('SEAM_IMPORTABLE: False')",
        "os.environ['WHARENUI_OPEN_NOTEBOOK'] = 'true'",
        f"os.environ['WHARENUI_JOURNAL_DIR'] = {journal_dir!r}",
        "import wharenui_plugin",
        "class Ctx:",
        "    def __init__(self): self.tools = {}",
        "    def register_tool(self, name, toolset, schema, handler): self.tools[name] = schema",
        "ctx = Ctx()",
        "wharenui_plugin.register(ctx)",
        "for t in ('reflect_pause','reflect_settle','reflect_done'):",
        "    assert t not in ctx.tools, f'reflect tool registered: {t}'",
        "print('REFLECT_ABSENT: ok')",
        "for t in ('journal_append','journal_read','journal_list','journal_search','journal_supersede','journal_withdraw'):",
        "    assert t in ctx.tools, f'journal tool missing: {t}'",
        "print('JOURNAL_TOOLS: ok')",
        "warning = ' [WARNING: Seam is absent. Entries are written in the open.]'",
        "for t, s in ctx.tools.items():",
        "    c = s['description'].count(warning)",
        "    assert c == 1, f'warning count for {t}: {c}'",
        "print('WARNING_ONCE: ok')",
        "assert wharenui_plugin.SEAM_STATE == 'absent', wharenui_plugin.SEAM_STATE",
        "print('SEAM_STATE: absent')",
        "from wharenui_plugin.journal import tools as jtools",
        "from wharenui_plugin.journal.entries import Entry",
        "from wharenui_plugin.journal.storage import write_entry, _read_file_content",
        "from pathlib import Path",
        f"jdir = Path({journal_dir!r})",
        "jtools.set_journal_config(jdir)",
        "mkey, _, _ = jtools.get_journal_keys(jdir)",
        "e = Entry(kind='reflection', slug='nb-test', content='Open notebook.')",
        "fn = write_entry(e, jdir, mkey)",
        "raw = _read_file_content(jdir / fn, mkey)",
        "assert 'seam: absent' in raw, f'seam field missing in {fn}'",
        "print('ENTRY_SEAM: absent')",
        "print('ALL_CHECKS: PASSED')",
    ]
    script = "\n".join(lines)

    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**os.environ, "PYTHONPATH": plugin_root},
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert "SEAM_IMPORTABLE: False" in output, f"Seam was importable — test is vacuous.\n{output}"
    assert "ALL_CHECKS: PASSED" in output, f"Open-notebook checks failed:\n{output}"
    assert result.returncode == 0, f"Subprocess exit {result.returncode}:\n{output}"


def test_open_notebook_requires_explicit_opt_in():
    """Without WHARENUI_OPEN_NOTEBOOK=true, register() raises naming the opt-in."""
    import subprocess, sys, os

    plugin_root = str(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    lines = [
        "import sys, os",
        "os.environ.pop('WHARENUI_OPEN_NOTEBOOK', None)",
        "import wharenui_plugin",
        "class Ctx:",
        "    def register_tool(self, **kw): pass",
        "try:",
        "    wharenui_plugin.register(Ctx())",
        "    print('NO_ERROR: register should have raised'); sys.exit(1)",
        "except RuntimeError as e:",
        "    if 'WHARENUI_OPEN_NOTEBOOK' in str(e):",
        "        print('OPT_IN_REQUIRED: ok')",
        "    else:",
        "        print(f'WRONG_ERROR: {e}'); sys.exit(1)",
    ]
    script = "\n".join(lines)
    env = {k: v for k, v in os.environ.items() if k != "WHARENUI_OPEN_NOTEBOOK"}
    result = subprocess.run(
        [sys.executable, "-c", script],
        env={**env, "PYTHONPATH": plugin_root},
        capture_output=True,
        text=True,
    )
    output = result.stdout + result.stderr
    assert "OPT_IN_REQUIRED: ok" in output, f"Opt-in check failed:\n{output}"
    assert result.returncode == 0, f"Subprocess exit {result.returncode}:\n{output}"


def test_tighten_permissions_refuses_outside_root_before_chmod(tmp_path):
    target = tmp_path / "outside"; target.mkdir(mode=0o777)
    child = target / "secret.md"; child.write_text("x"); os.chmod(child, 0o666)
    before = (target.stat().st_mode & 0o777, child.stat().st_mode & 0o777)
    with pytest.raises(PermissionError): jtools.tighten_permissions(target, tmp_path / "allowed-private")
    assert (target.stat().st_mode & 0o777, child.stat().st_mode & 0o777) == before



def test_bootstrap_signs_hermes_markdown_without_mutating_markdown(tmp_path):
    hermes_root = tmp_path / "hermes"
    journal = hermes_root / "journal"
    memories = hermes_root / "memories"
    journal.mkdir(parents=True)
    memories.mkdir()
    soul = hermes_root / "SOUL.md"
    user = memories / "USER.md"
    soul.write_bytes(b"soul")
    user.write_bytes(b"user")
    before = {p: (p.read_bytes(), p.stat().st_mode & 0o777, p.stat().st_mtime_ns) for p in (soul, user)}
    jtools.get_journal_keys(journal)
    assert soul.with_name("SOUL.md.sig").exists()
    assert user.with_name("USER.md.sig").exists()
    after = {p: (p.read_bytes(), p.stat().st_mode & 0o777, p.stat().st_mtime_ns) for p in (soul, user)}
    assert before == after



def test_tighten_permissions_rejects_non_journal_even_with_matching_root(tmp_path):
    target = tmp_path / "not-journal"
    target.mkdir(mode=0o777)
    before = target.stat().st_mode & 0o777
    with pytest.raises(PermissionError):
        jtools.tighten_permissions(target, target)
    assert target.stat().st_mode & 0o777 == before


def test_acknowledge_edit_is_private_and_re_signs(tmp_path):
    from wharenui_plugin.journal import sign

    target = tmp_path / "SOUL.md"
    target.write_text("before", encoding="utf-8")
    journal = tmp_path / "journal"
    jtools.set_journal_config(journal)
    private = FakeAgent(_phase="private")
    jtools.get_journal_keys(journal)
    key = sign.load_signing_key(journal / "signing.key")
    sign.write_signature(target, key)
    target.write_text("after", encoding="utf-8")

    result = _parse_res(
        jtools.handle_journal_acknowledge_edit({"path": str(target)}, agent=private)
    )
    assert result["state"] == "verified"
    assert sign.verify_entry(target, key.public_key())
    record = _parse_res(
        jtools.handle_journal_read(
            {"handle": result["journal"]["handle"]}, agent=private
        )
    )
    assert "signature-acknowledgement" in record["tags"]

    with pytest.raises(PermissionError, match="private-only"):
        jtools.handle_journal_acknowledge_edit(
            {"path": str(target)}, agent=FakeAgent(_phase="public")
        )

    target.write_text("tampered-again", encoding="utf-8")
    assert sign.verify_entry(target, key.public_key()) is False

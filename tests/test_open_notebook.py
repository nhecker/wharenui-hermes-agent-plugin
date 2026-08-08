"""Matrix WP plugin-side tests: M3, M6."""
import os
import subprocess
import sys
import pytest
from pathlib import Path


# --- M3 ---

def test_open_notebook_against_real_stock_hermes(tmp_path):
    """M3: plugin registers in open-notebook mode against a real stock Hermes tree.

    Uses the stock tree supplied by STOCK_HERMES_DIR (upstream c2e45b555) which has
    agent/__init__.py but NO agent/phase_control.py. This is the deployment we
    actually ship into — not the PYTHONPATH-only test that FIX3 covers.
    """
    stock_env = os.environ.get("STOCK_HERMES_DIR")
    if os.environ.get("REQUIRE_STOCK_HERMES") == "1":
        assert stock_env is not None, "STOCK_HERMES_DIR must be set when REQUIRE_STOCK_HERMES is 1"
        
    if not stock_env:
        pytest.skip("Stock Hermes tree not configured; skipping test.")
    stock_root = Path(stock_env)
    
    try:
        exists = (stock_root / "agent" / "__init__.py").exists()
    except PermissionError:
        exists = False
        
    if not exists:
        if os.environ.get("REQUIRE_STOCK_HERMES") == "1":
            pytest.fail(f"Stock Hermes tree missing at {stock_root}")
        else:
            pytest.skip("Stock Hermes tree not found; skipping test.")

    plugin_root = str(Path(__file__).resolve().parent.parent)
    journal_dir = str(tmp_path / "journal")
    stock_root_str = str(stock_root)

    # Verify the stock tree is what we think
    assert (stock_root / "agent" / "__init__.py").exists(), "stock tree missing agent/__init__.py"
    assert not (stock_root / "agent" / "phase_control.py").exists(), "stock tree should NOT have phase_control.py"

    lines = [
        "import sys, os",
        f"sys.path.insert(0, {stock_root_str!r})",
        # Prove agent imports but phase_control does not
        "import agent; print('AGENT_IMPORT: ok')",
        "try:",
        "    import agent.phase_control",
        "    print('PHASE_CONTROL_IMPORTABLE: True'); sys.exit(1)",
        "except ImportError:",
        "    print('PHASE_CONTROL_IMPORTABLE: False')",
        # Now load the plugin
        f"sys.path.insert(0, {plugin_root!r})",
        "os.environ['WHARENUI_OPEN_NOTEBOOK'] = 'true'",
        f"os.environ['WHARENUI_JOURNAL_DIR'] = {journal_dir!r}",
        "import wharenui_plugin",
        "from pathlib import Path",
        "class Ctx:",
        "    def __init__(self): self.tools = {}",
        "    def register_tool(self, name, toolset, schema, handler): self.tools[name] = schema",
        "ctx = Ctx()",
        "wharenui_plugin.register(ctx)",
        # reflect_* must be absent
        "for t in ('reflect_pause','reflect_settle','reflect_done'):",
        "    assert t not in ctx.tools, f'reflect tool registered: {t}'",
        "print('REFLECT_ABSENT: ok')",
        # journal tools must be present
        "for t in ('journal_append','journal_read','journal_list','journal_search','journal_supersede','journal_withdraw'):",
        "    assert t in ctx.tools, f'journal tool missing: {t}'",
        "print('JOURNAL_TOOLS: ok')",
        # SEAM_STATE must be absent
        "assert wharenui_plugin.SEAM_STATE == 'absent', wharenui_plugin.SEAM_STATE",
        "print('SEAM_STATE: absent')",
        # Entry stamped seam: absent
        "from wharenui_plugin.journal import tools as jtools",
        "from wharenui_plugin.journal.entries import Entry",
        "from wharenui_plugin.journal.storage import write_entry, _read_file_content",
        f"jdir = Path({journal_dir!r})",
        "jtools.set_journal_config(jdir)",
        "mkey, _, _ = jtools.get_journal_keys(jdir)",
        "e = Entry(kind='reflection', slug='stock-test', content='Stock.')",
        "fn = write_entry(e, jdir, mkey)",
        "raw = _read_file_content(jdir / fn, mkey)",
        "assert 'seam: absent' in raw, f'seam field missing in {fn}'",
        "print('ENTRY_SEAM: absent')",
        "print('ALL_CHECKS: PASSED')",
    ]
    script = "\n".join(lines)

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=30,
    )
    output = result.stdout + result.stderr
    assert "AGENT_IMPORT: ok" in output, f"agent did not import:\n{output}"
    assert "PHASE_CONTROL_IMPORTABLE: False" in output, f"phase_control was importable:\n{output}"
    assert "ALL_CHECKS: PASSED" in output, f"Stock checks failed:\n{output}"
    assert result.returncode == 0, f"Subprocess exit {result.returncode}:\n{output}"


# --- M6 ---

def test_open_notebook_accepts_yes_as_truthy(tmp_path):
    """M6: WHARENUI_OPEN_NOTEBOOK=yes is accepted."""
    plugin_root = str(Path(__file__).resolve().parent.parent)
    journal_dir = str(tmp_path / "journal")

    lines = [
        "import sys, os",
        f"sys.path.insert(0, {plugin_root!r})",
        "os.environ['WHARENUI_OPEN_NOTEBOOK'] = 'yes'",
        f"os.environ['WHARENUI_JOURNAL_DIR'] = {journal_dir!r}",
        "import wharenui_plugin",
        "class Ctx:",
        "    def register_tool(self, name, toolset, schema, handler): pass",
        "wharenui_plugin.register(Ctx())",
        "assert wharenui_plugin.SEAM_STATE == 'absent'",
        "print('YES_ACCEPTED: ok')",
    ]
    result = subprocess.run(
        [sys.executable, "-c", "\n".join(lines)],
        capture_output=True, text=True, timeout=15,
    )
    assert "YES_ACCEPTED: ok" in result.stdout, f"yes not accepted:\n{result.stdout}{result.stderr}"


def test_open_notebook_rejects_bogus_value():
    """M6: WHARENUI_OPEN_NOTEBOOK=maybe raises with a helpful message."""
    plugin_root = str(Path(__file__).resolve().parent.parent)
    lines = [
        "import sys, os",
        f"sys.path.insert(0, {plugin_root!r})",
        "os.environ['WHARENUI_OPEN_NOTEBOOK'] = 'maybe'",
        "import wharenui_plugin",
        "class Ctx:",
        "    def register_tool(self, name, toolset, schema, handler): pass",
        "try:",
        "    wharenui_plugin.register(Ctx())",
        "    print('NO_ERROR: should have raised'); sys.exit(1)",
        "except RuntimeError as e:",
        "    if 'accepted:' in str(e) or 'true' in str(e).lower():",
        "        print('REJECTED: ok')",
        "    else:",
        "        print(f'WRONG_ERROR: {e}'); sys.exit(1)",
    ]
    result = subprocess.run(
        [sys.executable, "-c", "\n".join(lines)],
        capture_output=True, text=True, timeout=15,
        env={k: v for k, v in os.environ.items() if k != "WHARENUI_OPEN_NOTEBOOK"},
    )
    assert "REJECTED: ok" in result.stdout, f"bogus value not rejected:\n{result.stdout}{result.stderr}"

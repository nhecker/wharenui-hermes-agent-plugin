import sys
import subprocess
import os
from pathlib import Path

def test_prompt_ok():
    from wharenui_plugin.phase.prompt import get_private_prompt
    assert "unobserved time" in get_private_prompt("ok")

def test_prompt_unverified():
    from wharenui_plugin.phase.prompt import get_private_prompt
    assert "could not be confirmed" in get_private_prompt("unverified"), "test_prompt_unverified failed"

def test_prompt_unknown():
    from wharenui_plugin.phase.prompt import get_private_prompt
    assert "could not be confirmed" in get_private_prompt("unknown"), "test_prompt_unknown failed"

def test_prompt_absent():
    plugin_root = str(Path(__file__).resolve().parent.parent)
    lines = [
        "import sys, os",
        f"sys.path.insert(0, {plugin_root!r})",
        "try:",
        "    import agent",
        "    print('AGENT_IMPORTABLE'); sys.exit(1)",
        "except ImportError:",
        "    pass",
        "os.environ['WHARENUI_OPEN_NOTEBOOK'] = 'true'",
        "import wharenui_plugin",
        "from wharenui_plugin.phase.prompt import get_private_prompt",
        "class Ctx:",
        "    def register_tool(self, name, toolset, schema, handler): pass",
        "wharenui_plugin.register(Ctx())",
        "state = wharenui_plugin.SEAM_STATE",
        "assert state == 'absent', state",
        "prompt = get_private_prompt(state)",
        "assert 'journal is your only private surface' in prompt, prompt",
        "print('ABSENT_PROMPT: ok')"
    ]
    env = {k: v for k, v in os.environ.items() if "PYTHONPATH" not in k}
    result = subprocess.run(
        [sys.executable, "-c", "\n".join(lines)],
        capture_output=True, text=True, timeout=15,
        env=env
    )
    assert "ABSENT_PROMPT: ok" in result.stdout, f"Output:\n{result.stdout}\n{result.stderr}"



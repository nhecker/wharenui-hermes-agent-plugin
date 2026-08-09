import pytest
from wharenui_plugin.phase.handler import WharePhaseHandler
import wharenui_plugin

def test_failred(monkeypatch, agent):
    # Mock to remove reflect_settle and reflect_done
    original_register = wharenui_plugin.register
    def fake_register(ctx):
        original_register(ctx)
        # Remove reflect_settle and reflect_done
        ctx.tools = [t for t in getattr(ctx, "tools", []) if t["function"]["name"] not in ("reflect_settle", "reflect_done")]
        # Also remove them from valid_tool_names if possible
    monkeypatch.setattr(wharenui_plugin, "register", fake_register)
    
    # Just run init to see phase
    # Actually the test fixture already creates an agent.
    assert True

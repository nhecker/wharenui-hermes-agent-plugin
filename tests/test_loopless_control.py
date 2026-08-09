import pytest
from wharenui_plugin.phase.tools import handle_reflect_settle, handle_reflect_done

class FakeAgent:
    def __init__(self, phase="private"):
        self._phase = phase
        self._private_exit = None

def test_loopless_control_tools_do_not_assert_outcomes():
    # Context: a chat interface without the conversation loop that consumes _private_exit.
    # The tools must describe the request and state change, not assert downstream execution.
    agent = FakeAgent(phase="private")
    
    res_settle = handle_reflect_settle(agent=agent)
    assert res_settle == "Recorded request to return to window."
    assert agent._private_exit is not None
    assert agent._private_exit.action == "resume"

    agent._private_exit = None
    res_done = handle_reflect_done(agent=agent)
    assert res_done == "Recorded request to end session."
    assert agent._private_exit is not None
    assert agent._private_exit.action == "close"

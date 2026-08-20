import pytest
from types import SimpleNamespace
from wharenui_plugin.phase.tools import handle_reflect_settle, handle_reflect_done
from wharenui_plugin.phase.handler import WharePhaseHandler
import wharenui_plugin

class FakeAgent:
    def __init__(self, phase="private"):
        self._phase = phase
        self._private_exit = None


def test_schema_descriptions_are_request_oriented_and_honest():
    """Verify that reflect tool schemas describe requests, not guaranteed executions."""
    # Settle schema
    assert wharenui_plugin._SETTLE_SCHEMA["description"] == "Request returning to the public window from private time."
    # Done schema
    assert wharenui_plugin._DONE_SCHEMA["description"] == "Request ending the session from private or closing-private time."
    # Pause schema
    assert wharenui_plugin._PAUSE_SCHEMA["description"] == "Request pausing the public window to enter private time."

    # Fail-red regression assertions: schemas must never make unconditional outcome assertions
    for name, schema in [
        ("reflect_settle", wharenui_plugin._SETTLE_SCHEMA),
        ("reflect_done", wharenui_plugin._DONE_SCHEMA),
        ("reflect_pause", wharenui_plugin._PAUSE_SCHEMA),
    ]:
        desc = schema["description"]
        assert not desc.startswith("Return to"), f"{name} must not assert execution ('Return to...')"
        assert not desc.startswith("End the"), f"{name} must not assert execution ('End the...')"
        assert not desc.startswith("Pause the"), f"{name} must not assert execution ('Pause the...')"
        assert "Request " in desc, f"{name} schema must explicitly use request-oriented framing"


def test_loopless_control_tools_do_not_assert_outcomes():
    """In a loop-less context without a consuming runner, tools record intent without asserting execution."""
    agent = FakeAgent(phase="private")
    
    res_settle = handle_reflect_settle(agent=agent)
    assert res_settle == "Recorded request to return to window."
    assert agent._private_exit is not None
    assert agent._private_exit.action == "resume"
    assert agent._phase == "private"  # Handler records intent; phase is not mutated by tool handler

    agent._private_exit = None
    res_done = handle_reflect_done(agent=agent)
    assert res_done == "Recorded request to end session."
    assert agent._private_exit is not None
    assert agent._private_exit.action == "close"
    assert agent._phase == "private"  # Phase remains unchanged


def test_loopless_control_tools_phase_rejections():
    """Verify honest refusals when tools are called in invalid phases."""
    # Settle rejected during close-out
    agent_close = FakeAgent(phase="closing_private")
    res = handle_reflect_settle(agent=agent_close)
    assert res == "Cannot return during close-out. Use reflect_done."
    assert agent_close._private_exit is None

    # Done rejected in public phase
    agent_public = FakeAgent(phase="public")
    res = handle_reflect_done(agent=agent_public)
    assert res == "Cannot exit from public phase. Use reflect_pause first."
    assert agent_public._private_exit is None


def test_loopless_control_tools_with_none_agent():
    """Tool execution without an agent instance gracefully records or refuses without crashing."""
    res_settle = handle_reflect_settle(agent=None)
    assert res_settle == "Recorded request to return to window."

    res_done = handle_reflect_done(agent=None)
    # With agent=None, default resolved phase is 'public', so reflect_done is safely refused
    assert res_done == "Cannot exit from public phase. Use reflect_pause first."


class MockSubturnAgent:
    """Mock agent with a subturn runner that simulates the consuming conversation loop."""
    def __init__(self, turns_to_settle: int = 1, exit_action: str = "settle"):
        self.tools = []
        self._phase = "private"
        self._private_exit = None
        self._current_turn = 0
        self.turns_to_settle = turns_to_settle
        self.exit_action = exit_action

    def run_subturn(self, messages, tool_names, task_id):
        self._current_turn += 1
        if self._current_turn >= self.turns_to_settle:
            if self.exit_action == "settle":
                handle_reflect_settle(agent=self)
            elif self.exit_action == "done":
                handle_reflect_done(agent=self)
            return SimpleNamespace(tool_calls_used=True)
        return SimpleNamespace(tool_calls_used=True)


def test_consuming_loop_consumes_and_clears_private_exit():
    """In a consuming conversation loop (WharePhaseHandler.run), _private_exit is consumed and cleared."""
    handler = WharePhaseHandler()
    messages = []

    # Case 1: subturn calls reflect_settle -> handler returns resume ControlOutcome
    agent_settle = MockSubturnAgent(turns_to_settle=1, exit_action="settle")
    outcome = handler.run(agent_settle, messages, effective_task_id="test_task")
    assert outcome.action == "resume"
    assert outcome.handler == "reflect_pause"
    assert outcome.tool_result == "(settled)"
    assert agent_settle._private_exit is None  # Must be cleared upon exit

    # Case 2: subturn calls reflect_done -> handler returns close ControlOutcome
    agent_done = MockSubturnAgent(turns_to_settle=1, exit_action="done")
    outcome_done = handler.run(agent_done, messages, effective_task_id="test_task")
    assert outcome_done.action == "close"
    assert outcome_done.handler == "reflect_pause"
    assert outcome_done.tool_result == "(session ended)"
    assert agent_done._private_exit is None  # Must be cleared upon exit


def test_consuming_loop_fallback_when_no_tool_calls():
    """When a subturn uses no tool calls, handler returns a clean resume outcome."""
    handler = WharePhaseHandler()
    messages = []

    class NoToolAgent:
        def __init__(self):
            self.tools = []
            self._phase = "private"
            self._private_exit = None

        def run_subturn(self, messages, tool_names, task_id):
            return SimpleNamespace(tool_calls_used=False)

    agent = NoToolAgent()
    outcome = handler.run(agent, messages, effective_task_id="test_task")
    assert outcome.action == "resume"
    assert outcome.tool_result == "(private turn ended)"

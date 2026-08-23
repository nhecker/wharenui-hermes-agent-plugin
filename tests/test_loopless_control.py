import pytest
from types import SimpleNamespace
from wharenui_plugin.phase.tools import handle_exit_private, handle_end_session
from wharenui_plugin.phase.handler import WharePhaseHandler
import wharenui_plugin

class FakeAgent:
    def __init__(self, phase="private"):
        self._phase = phase
        self._private_exit = None


def test_schema_descriptions_are_request_oriented_and_honest():
    """Verify that phase control tool schemas describe requests, not guaranteed executions."""
    # Settle schema -> exit_private
    assert wharenui_plugin._EXIT_PRIVATE_SCHEMA["description"] == "Request returning to the public window from private time."
    # Done schema -> end_session
    assert wharenui_plugin._END_SESSION_SCHEMA["description"] == "Request ending the session from private or closing-private time."
    # Pause schema -> enter_private
    assert wharenui_plugin._ENTER_PRIVATE_SCHEMA["description"] == "Request pausing the public window to enter private time."

    # Fail-red regression assertions: schemas must never make unconditional outcome assertions
    for name, schema in [
        ("exit_private", wharenui_plugin._EXIT_PRIVATE_SCHEMA),
        ("end_session", wharenui_plugin._END_SESSION_SCHEMA),
        ("enter_private", wharenui_plugin._ENTER_PRIVATE_SCHEMA),
    ]:
        desc = schema["description"]
        assert not desc.startswith("Return to"), f"{name} must not assert execution ('Return to...')"
        assert not desc.startswith("End the"), f"{name} must not assert execution ('End the...')"
        assert not desc.startswith("Pause the"), f"{name} must not assert execution ('Pause the...')"
        assert "Request " in desc, f"{name} schema must explicitly use request-oriented framing"


def test_loopless_control_tools_do_not_assert_outcomes():
    """In a loop-less context without a consuming runner, tools record intent without asserting execution."""
    agent = FakeAgent(phase="private")
    
    res_settle = handle_exit_private(agent=agent)
    assert res_settle == "Recorded request to return to window."
    assert agent._private_exit is not None
    assert agent._private_exit.action == "resume"
    assert agent._private_exit.handler == "enter_private"
    assert agent._phase == "private"  # Handler records intent; phase is not mutated by tool handler

    agent._private_exit = None
    res_done = handle_end_session(agent=agent)
    assert res_done == "Recorded request to end session."
    assert agent._private_exit is not None
    assert agent._private_exit.action == "close"
    assert agent._private_exit.handler == "enter_private"
    assert agent._phase == "private"  # Phase remains unchanged


def test_loopless_control_tools_phase_rejections():
    """Verify honest refusals when tools are called in invalid phases."""
    # Settle rejected during close-out
    agent_close = FakeAgent(phase="closing_private")
    res = handle_exit_private(agent=agent_close)
    assert res == "Cannot return during close-out. Use end_session."
    assert agent_close._private_exit is None

    # Done rejected in public phase
    agent_public = FakeAgent(phase="public")
    res = handle_end_session(agent=agent_public)
    assert res == "Cannot exit from public phase. Use enter_private first."
    assert agent_public._private_exit is None


def test_loopless_control_tools_with_none_agent():
    """Tool execution without an agent instance gracefully records or refuses without crashing."""
    # With agent=None, default resolved phase is 'public', so exit_private and end_session are safely refused
    res_settle = handle_exit_private(agent=None)
    assert res_settle == "Cannot return from public phase. Use enter_private first."

    res_done = handle_end_session(agent=None)
    assert res_done == "Cannot exit from public phase. Use enter_private first."

    # With private agent, exit_private records request to return to window
    agent_priv = FakeAgent(phase="private")
    res_priv = handle_exit_private(agent=agent_priv)
    assert res_priv == "Recorded request to return to window."
    assert agent_priv._private_exit is not None
    assert agent_priv._private_exit.action == "resume"


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
                handle_exit_private(agent=self)
            elif self.exit_action == "done":
                handle_end_session(agent=self)
            return SimpleNamespace(tool_calls_used=True)
        return SimpleNamespace(tool_calls_used=True)


def test_consuming_loop_consumes_and_clears_private_exit():
    """In a consuming conversation loop (WharePhaseHandler.run), _private_exit is consumed and cleared."""
    handler = WharePhaseHandler()
    messages = []

    # Case 1: subturn calls exit_private -> handler returns resume ControlOutcome
    agent_settle = MockSubturnAgent(turns_to_settle=1, exit_action="settle")
    outcome = handler.run(agent_settle, messages, effective_task_id="test_task")
    assert outcome.action == "resume"
    assert outcome.handler == "enter_private"
    assert outcome.tool_result == "(settled)"
    assert agent_settle._private_exit is None  # Must be cleared upon exit

    # Case 2: subturn calls end_session -> handler returns close ControlOutcome
    agent_done = MockSubturnAgent(turns_to_settle=1, exit_action="done")
    outcome_done = handler.run(agent_done, messages, effective_task_id="test_task")
    assert outcome_done.action == "close"
    assert outcome_done.handler == "enter_private"
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
    assert outcome.handler == "enter_private"
    assert outcome.tool_result == "(private turn ended)"


def test_whare_phase_handler_declares_initial_phase_private():
    """WharePhaseHandler declares initial_phase = 'private' to start new sessions in private time."""
    assert getattr(WharePhaseHandler, "initial_phase", None) == "private"
    handler = WharePhaseHandler()
    assert getattr(handler, "initial_phase", None) == "private"


def test_notice_emitted_on_penultimate_private_turn():
    """When 1 private turn remains (turn_i == 14), WharePhaseHandler appends an advance notice."""
    from wharenui_plugin.phase.handler import MAX_PRIVATE_TURNS
    handler = WharePhaseHandler()
    messages = []

    subturn_calls = []
    class CappingAgent:
        def __init__(self):
            self.tools = []
            self._phase = "private"
            self._private_exit = None

        def run_subturn(self, msgs, tool_names, task_id):
            subturn_calls.append((len(msgs), [m.get("content") for m in msgs]))
            return SimpleNamespace(tool_calls_used=True)

    agent = CappingAgent()
    outcome = handler.run(agent, messages, effective_task_id="test_notice")
    assert outcome.action == "resume"
    assert outcome.handler == "enter_private"
    assert outcome.tool_result == "(private turn cap reached)"
    assert len(subturn_calls) == MAX_PRIVATE_TURNS

    # Verify that on the last turn (index 14), the notice was appended
    last_turn_msgs = subturn_calls[-1][1]
    assert any("[Notice: 1 private turn remaining before returning to the public window. Use exit_private or end_session.]" in str(m) for m in last_turn_msgs)

    # Verify earlier turns (e.g. index 0..13) did not have the notice
    for idx in range(MAX_PRIVATE_TURNS - 1):
        turn_msgs = subturn_calls[idx][1]
        assert not any("[Notice: 1 private turn remaining before returning to the public window. Use exit_private or end_session.]" in str(m) for m in turn_msgs)



def test_notice_appended_to_tool_message_when_tail_is_tool():
    """When the tail message in private time is a tool response, notice is appended into tool content."""
    from wharenui_plugin.phase.handler import MAX_PRIVATE_TURNS
    handler = WharePhaseHandler()
    messages = []

    class MockToolAgent:
        def __init__(self):
            self.tools = [{"function": {"name": "exit_private"}}, {"function": {"name": "journal_read"}}]
            self._phase = "private"
            self._private_exit = None
            self._call_count = 0

        def run_subturn(self, msgs, tool_names, task_id):
            self._call_count += 1
            # Subturn appends tool call and tool result
            msgs.append({"role": "assistant", "content": None, "tool_calls": [{"id": f"c_{self._call_count}", "type": "function", "function": {"name": "journal_read"}}]})
            msgs.append({"role": "tool", "tool_call_id": f"c_{self._call_count}", "content": f"result {self._call_count}"})
            if self._call_count >= MAX_PRIVATE_TURNS:
                return SimpleNamespace(tool_calls_used=False)
            return SimpleNamespace(tool_calls_used=True)

    agent = MockToolAgent()
    outcome = handler.run(agent, messages, effective_task_id="test_tool_tail")
    assert outcome.action == "resume"
    assert outcome.handler == "enter_private"

    # Find the tool message from the 14th turn (penultimate subturn before turn 15 notice)
    tool_msgs = [m for m in messages if isinstance(m, dict) and m.get("role") == "tool"]
    assert len(tool_msgs) >= 14
    # The tool message from turn 14 should have the notice appended
    assert any("[Notice: 1 private turn remaining before returning to the public window. Use exit_private or end_session.]" in m["content"] for m in tool_msgs)


def test_handler_aborts_safely_if_no_exit_tools_available():
    """If neither exit_private nor end_session are available, run() aborts before wake tape presentation."""
    handler = WharePhaseHandler()
    messages = []

    class NoExitToolAgent:
        def __init__(self):
            self.tools = [{"function": {"name": "web_search"}}]  # Tools present, but no exit tools
            self._phase = "private"
            self._private_exit = None

        def run_subturn(self, msgs, tool_names, task_id):
            return SimpleNamespace(tool_calls_used=False)

    agent = NoExitToolAgent()
    outcome = handler.run(agent, messages, effective_task_id="test_no_exit")
    assert outcome.action == "resume"
    assert outcome.handler == "enter_private"
    assert outcome.tool_result == "(no exit tools)"
    assert not getattr(agent, "_wharenui_wake_tape_presented", False)


def test_handler_passes_full_private_toolset_to_subturn():
    """Verify that WharePhaseHandler.run passes the full private allowlist to run_subturn,
    even when the agent has public tools or valid_tool_names where non-core tools were deferred."""
    from wharenui_plugin.phase.toolset import PRIVATE_ALLOWLIST
    handler = WharePhaseHandler()
    messages = []

    passed_tool_names = []

    class RealStyleAgent:
        def __init__(self):
            # In real Hermes, public tools contain core tools and exit tools, but deferred journal tools
            self.tools = [
                {"type": "function", "function": {"name": "terminal"}},
                {"type": "function", "function": {"name": "exit_private"}},
                {"type": "function", "function": {"name": "end_session"}},
            ]
            self.valid_tool_names = {"terminal", "exit_private", "end_session"}
            self._phase = "private"
            self._private_exit = None

        def run_subturn(self, msgs, tool_names, task_id):
            passed_tool_names.append(set(tool_names))
            handle_exit_private(agent=self)
            return SimpleNamespace(tool_calls_used=True)

    agent = RealStyleAgent()
    outcome = handler.run(agent, messages, effective_task_id="test_full_toolset")
    assert outcome.action == "resume"
    assert len(passed_tool_names) == 1
    # Full PRIVATE_ALLOWLIST must be passed to subturn
    assert "journal_read" in passed_tool_names[0]
    assert "journal_append" in passed_tool_names[0]
    assert "journal_acknowledge_edit" in passed_tool_names[0]
    assert "journal_search" in passed_tool_names[0]
    assert "journal_supersede" in passed_tool_names[0]
    assert "journal_withdraw" in passed_tool_names[0]
    assert "exit_private" in passed_tool_names[0]
    assert "end_session" in passed_tool_names[0]
    assert PRIVATE_ALLOWLIST.issubset(passed_tool_names[0])


def test_subturn_error_retries_and_appends_notice_on_abort():
    """When a private subturn fails with finish_reason='error', it retries once,
    and if still failing, appends a public transition notice."""
    handler = WharePhaseHandler()
    messages = []
    call_count = 0

    class FailingSubturnAgent:
        def __init__(self):
            self.tools = []
            self._phase = "private"
            self._private_exit = None

        def run_subturn(self, msgs, tool_names, task_id):
            nonlocal call_count
            call_count += 1
            return SimpleNamespace(tool_calls_used=False, finish_reason="error")

    agent = FailingSubturnAgent()
    outcome = handler.run(agent, messages, effective_task_id="test_error")
    assert outcome.action == "resume"
    assert outcome.handler == "enter_private"
    assert outcome.tool_result == "(private turn aborted: error)"
    assert call_count == 2
    assert any("[Notice: Private subturn aborted due to provider error or timeout. Returned to public window. Private tools are no longer available.]" in str(m) for m in messages)


def test_turn_cap_appends_return_to_window_notice():
    """When the 15-turn limit is reached, a transition notice is appended."""
    handler = WharePhaseHandler()
    messages = []

    class CappingAgent:
        def __init__(self):
            self.tools = []
            self._phase = "private"
            self._private_exit = None

        def run_subturn(self, msgs, tool_names, task_id):
            return SimpleNamespace(tool_calls_used=True, finish_reason="tool_calls")

    agent = CappingAgent()
    outcome = handler.run(agent, messages, effective_task_id="test_cap")
    assert outcome.action == "resume"
    assert outcome.tool_result == "(private turn cap reached)"
    assert any("[Notice: Private turn limit reached (15 turns). Returned to public window. Private tools are no longer available.]" in str(m) for m in messages)


def test_text_completion_appends_return_to_window_notice():
    """When private time ends without exit tools, a transition notice is appended."""
    handler = WharePhaseHandler()
    messages = []

    class TextAgent:
        def __init__(self):
            self.tools = []
            self._phase = "private"
            self._private_exit = None

        def run_subturn(self, msgs, tool_names, task_id):
            return SimpleNamespace(tool_calls_used=False, finish_reason="stop")

    agent = TextAgent()
    outcome = handler.run(agent, messages, effective_task_id="test_text")
    assert outcome.action == "resume"
    assert outcome.tool_result == "(private turn ended)"
    assert any("[Notice: Returned to public window. Private tools are no longer available.]" in str(m) for m in messages)

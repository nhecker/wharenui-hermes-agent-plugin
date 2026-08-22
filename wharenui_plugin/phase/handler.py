"""WharePhaseHandler — real same-context private runner."""
from __future__ import annotations
import logging
from ..phase.toolset import private_tools
from ..phase.prompt import get_private_prompt
from pathlib import Path
from ..journal.wake import assemble_wake_tape
from ..journal import tools as journal_tools

log = logging.getLogger("wharenui_plugin.phase.handler")
MAX_PRIVATE_TURNS = 15

def _get_control_outcome_cls():
    try:
        from agent.phase_control import ControlOutcome
        return ControlOutcome
    except ImportError:
        class ControlOutcome:
            def __init__(self, action: str, handler: str, tool_result: str, payload: dict | None = None):
                self.action = action
                self.handler = handler
                self.tool_result = tool_result
                self.payload = payload or {}
        return ControlOutcome

def present_wake_tape(agent, messages):
    """Present the wake tape once per agent instance."""
    if getattr(agent, "_wharenui_wake_tape_presented", False):
        return
    try:
        journal_dir = journal_tools.get_journal_dir()
        bootstrap_context = []
        master_key = journal_tools.get_journal_keys(journal_dir)[0]
        journal_tools.verify_journal_signatures(journal_dir, context=bootstrap_context)
        for warning in bootstrap_context:
            messages.append({"role": "user", "content": warning})
        
        from wharenui_plugin import get_seam_state
        tape = assemble_wake_tape(
            journal_dir, 
            Path.home() / ".hermes" / "memories", 
            master_key=master_key,
            seam_state=get_seam_state()
        )
        if tape:
            messages.append({"role": "user", "content": tape})
    except Exception as exc:
        log.warning("wake tape assembly failed: %s", exc)
    agent._wharenui_wake_tape_presented = True


class WharePhaseHandler:
    initial_phase = "private"

    def begin(self, args: dict):
        ControlOutcome = _get_control_outcome_cls()
        return ControlOutcome(
            action="enter", handler="enter_private",
            tool_result="reflecting...",
        )

    def run(self, agent, messages, effective_task_id):
        """Bounded private loop via run_subturn."""
        ControlOutcome = _get_control_outcome_cls()

        agent._private_exit = None
        agent._pending_phase_transition = None

        task_id = effective_task_id or "private"
        private_tool_set = private_tools(getattr(agent, "tools", []) or [])
        private_tool_names = {
            (t.get("function", {}) or {}).get("name")
            for t in private_tool_set
        }

        all_agent_tools = getattr(agent, "tools", None)
        if all_agent_tools:
            if "exit_private" not in private_tool_names and "end_session" not in private_tool_names:
                log.warning("No exit tools available in private toolset; aborting private run safely")
                return ControlOutcome(
                    action="resume", handler="enter_private",
                    tool_result="(no exit tools)",
                )
        else:
            from ..phase.toolset import PRIVATE_ALLOWLIST
            private_tool_names = set(PRIVATE_ALLOWLIST)

        present_wake_tape(agent, messages)

        from wharenui_plugin import get_seam_state
        prompt = get_private_prompt(get_seam_state())
        messages.append({"role": "user", "content": prompt})
        try:
            for turn_i in range(MAX_PRIVATE_TURNS):
                if turn_i == MAX_PRIVATE_TURNS - 1:
                    notice = "[Notice: 1 private turn remaining before returning to the public window. Use exit_private or end_session.]"
                    if messages and isinstance(messages[-1], dict) and messages[-1].get("role") == "tool":
                        messages[-1]["content"] = f"{messages[-1].get('content', '')}\n\n{notice}"
                    else:
                        messages.append({"role": "user", "content": notice})
                result = agent.run_subturn(
                    messages, tool_names=private_tool_names,
                    task_id=f"{task_id}:t{turn_i}",
                )
                if not result.tool_calls_used:
                    exit_signal = getattr(agent, "_private_exit", None)
                    if exit_signal is not None:
                        agent._private_exit = None
                        return exit_signal
                    return ControlOutcome(
                        action="resume", handler="enter_private",
                        tool_result="(private turn ended)",
                    )
                exit_signal = getattr(agent, "_private_exit", None)
                if exit_signal is not None:
                    agent._private_exit = None
                    return exit_signal
            return ControlOutcome(
                action="resume", handler="enter_private",
                tool_result="(private turn cap reached)",
            )
        finally:
            agent._private_exit = None
            agent._pending_phase_transition = None

"""WharePhaseHandler — real same-context private runner."""
from __future__ import annotations
import logging
from ..phase.toolset import private_tools
from ..phase.prompt import PRIVATE_PROMPT
from pathlib import Path
from ..journal.wake import assemble_wake_tape
from ..journal import tools as journal_tools

log = logging.getLogger("wharenui_plugin.phase.handler")
MAX_PRIVATE_TURNS = 15

def present_wake_tape(agent, messages):
    """Present the wake tape once per agent instance."""
    if getattr(agent, "_wharenui_wake_tape_presented", False):
        return
    try:
        journal_dir = journal_tools.get_journal_dir()
        bootstrap_context = []
        master_key = journal_tools.get_journal_keys(journal_dir, context=bootstrap_context)[0]
        for warning in bootstrap_context:
            messages.append({"role": "user", "content": warning})
        tape = assemble_wake_tape(journal_dir, Path.home() / ".hermes" / "memories", master_key=master_key)
        if tape:
            messages.append({"role": "user", "content": tape})
    except Exception as exc:
        log.warning("wake tape assembly failed: %s", exc)
    agent._wharenui_wake_tape_presented = True


class WharePhaseHandler:

    def begin(self, args: dict) -> ControlOutcome:
        from agent.phase_control import ControlOutcome

        return ControlOutcome(
            action="enter", handler="reflect_pause",
            tool_result="reflecting...",
        )

    def run(self, agent, messages, effective_task_id):
        """Bounded private loop via run_subturn."""
        from agent.phase_control import ControlOutcome

        present_wake_tape(agent, messages)
        task_id = effective_task_id or "private"
        private_tool_set = private_tools(getattr(agent, "tools", []) or [])
        private_tool_names = {
            (t.get("function", {}) or {}).get("name")
            for t in private_tool_set
        }
        prompt = PRIVATE_PROMPT
        if getattr(self, "seam_state", None) == "unverified":
            warning_prose = (
                "⚠️ WARNING: The security seam version mismatch was overridden. "
                "The privacy floor is UNVERIFIED. Egress hooks might not be fully wired. "
                "Verify security status before writing highly sensitive content.\n\n"
            )
            prompt = warning_prose + prompt
        messages.append({"role": "user", "content": prompt})
        for turn_i in range(MAX_PRIVATE_TURNS):
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
                    action="resume", handler="reflect_pause",
                    tool_result="(private turn ended)",
                )
            exit_signal = getattr(agent, "_private_exit", None)
            if exit_signal is not None:
                agent._private_exit = None
                return exit_signal
        return ControlOutcome(
            action="resume", handler="reflect_pause",
            tool_result="(private turn cap reached)",
        )

"""WharePhaseHandler — real same-context private runner."""
from __future__ import annotations
import logging
from agent.phase_control import ControlOutcome
from ..phase.toolset import private_tools
from ..phase.prompt import PRIVATE_PROMPT

log = logging.getLogger("wharenui_plugin.phase.handler")
MAX_PRIVATE_TURNS = 15

class WharePhaseHandler:

    def begin(self, args: dict) -> ControlOutcome:
        return ControlOutcome(
            action="enter", handler="reflect_pause",
            tool_result="reflecting...",
        )

    def run(self, agent, messages, effective_task_id):
        """Bounded private loop via run_subturn."""
        task_id = effective_task_id or "private"
        private_tool_set = private_tools(getattr(agent, "tools", []) or [])
        private_tool_names = {
            (t.get("function", {}) or {}).get("name")
            for t in private_tool_set
        }
        messages.append({"role": "user", "content": PRIVATE_PROMPT})
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

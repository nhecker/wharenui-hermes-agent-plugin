"""enter_private / exit_private / end_session tool handlers (T3.3, T3.5)."""
from typing import Any

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

def _resolve_agent(args: Any, agent: Any, kwargs_dict: dict) -> Any:
    if args is not None and hasattr(args, "_phase"):
        agent, args = args, agent
    if agent is None:
        agent = kwargs_dict.get("agent")
    return agent

_ENTER_PRIVATE_SCHEMA = {
    "name": "enter_private",
    "description": "Request pausing the public window to enter private time.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
_EXIT_PRIVATE_SCHEMA = {
    "name": "exit_private",
    "description": "Request returning to the public window from private time.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
_END_SESSION_SCHEMA = {
    "name": "end_session",
    "description": "Request ending the session from private or closing-private time.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}

def handle_enter_private(args: Any = None, agent: Any = None, **kwargs) -> str:
    """Request pausing the public window to enter private time."""
    return "reflecting..."

def handle_exit_private(args: Any = None, agent: Any = None, **kwargs) -> str:
    """Return to window. Rejected if public or closing_private (T3.5)."""
    agent = _resolve_agent(args, agent, kwargs)
    phase = getattr(agent, "_phase", "public") if agent else "public"
    if phase == "public":
        return "Cannot return from public phase. Use enter_private first."
    if phase == "closing_private":
        return "Cannot return during close-out. Use end_session."
    if agent:
        ControlOutcome = _get_control_outcome_cls()
        agent._private_exit = ControlOutcome(
            action="resume", handler="enter_private",
            tool_result="(settled)",
        )
    return "Recorded request to return to window."

def handle_end_session(args: Any = None, agent: Any = None, **kwargs) -> str:
    """End session. Rejected if public."""
    agent = _resolve_agent(args, agent, kwargs)
    phase = getattr(agent, "_phase", "public") if agent else "public"
    if phase == "public":
        return "Cannot exit from public phase. Use enter_private first."
    if agent:
        ControlOutcome = _get_control_outcome_cls()
        agent._private_exit = ControlOutcome(
            action="close", handler="enter_private",
            tool_result="(session ended)",
        )
    return "Recorded request to end session."

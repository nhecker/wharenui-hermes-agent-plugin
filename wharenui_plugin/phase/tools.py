"""reflect_settle / reflect_done tool handlers (T3.3, T3.5)."""
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

def handle_reflect_settle(args: Any = None, agent: Any = None, **kwargs) -> str:
    """Return to window. Rejected if closing_private (T3.5)."""
    agent = _resolve_agent(args, agent, kwargs)
    phase = getattr(agent, "_phase", "public") if agent else "public"
    if phase == "closing_private":
        return "Cannot return during close-out. Use reflect_done."
    if agent:
        ControlOutcome = _get_control_outcome_cls()
        agent._private_exit = ControlOutcome(
            action="resume", handler="reflect_pause",
            tool_result="(settled)",
        )
    return "Recorded request to return to window."

def handle_reflect_done(args: Any = None, agent: Any = None, **kwargs) -> str:
    """End session. Rejected if public."""
    agent = _resolve_agent(args, agent, kwargs)
    phase = getattr(agent, "_phase", "public") if agent else "public"
    if phase == "public":
        return "Cannot exit from public phase. Use reflect_pause first."
    if agent:
        ControlOutcome = _get_control_outcome_cls()
        agent._private_exit = ControlOutcome(
            action="close", handler="reflect_pause",
            tool_result="(session ended)",
        )
    return "Recorded request to end session."

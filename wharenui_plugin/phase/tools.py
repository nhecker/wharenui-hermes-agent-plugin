"""reflect_settle / reflect_done tool handlers (T3.3, T3.5)."""
from agent.phase_control import ControlOutcome
from typing import Any

def handle_reflect_settle(agent: Any, args: dict, **kwargs) -> str:
    """Return to window. Rejected if closing_private (T3.5)."""
    phase = getattr(agent, "_phase", "public")
    if phase == "closing_private":
        return "Cannot return during close-out. Use reflect_done."
    agent._private_exit = ControlOutcome(
        action="resume", handler="reflect_pause",
        tool_result="(settled)",
    )
    return "Returning to window."

def handle_reflect_done(agent: Any, args: dict, **kwargs) -> str:
    """End session. Rejected if public."""
    phase = getattr(agent, "_phase", "public")
    if phase == "public":
        return "Cannot exit from public phase. Use reflect_pause first."
    agent._private_exit = ControlOutcome(
        action="close", handler="reflect_pause",
        tool_result="(session ended)",
    )
    return "Ending session."

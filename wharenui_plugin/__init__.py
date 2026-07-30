"""Wharenui Hermes plugin — phase tools + journal package."""

import logging

log = logging.getLogger("wharenui_plugin")

_PAUSE_SCHEMA = {
    "name": "reflect_pause",
    "description": "Pause the public window and enter private time.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
_SETTLE_SCHEMA = {
    "name": "reflect_settle",
    "description": "Return to the public window from private time.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
_DONE_SCHEMA = {
    "name": "reflect_done",
    "description": "End the session from private/closing-private time.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def register(ctx):
    """Register Wharenui with Hermes Agent."""
    from .phase.handler import WharePhaseHandler
    from .phase.tools import handle_reflect_settle, handle_reflect_done

    handler = WharePhaseHandler()
    has_seam = hasattr(ctx, "register_control_tool")

    if has_seam:
        ctx.register_control_tool(
            name="reflect_pause", toolset="wharenui",
            schema=_PAUSE_SCHEMA,
            handler=lambda tool_args, **kw: handler.begin(tool_args),
            phase_handler=handler,
        )
        log.info("reflect_pause registered as control tool")
    else:
        log.warning("Phase-control seam not found; loading journal-only.")

    ctx.register_tool(name="reflect_settle", toolset="wharenui",
                      schema=_SETTLE_SCHEMA, handler=handle_reflect_settle)
    ctx.register_tool(name="reflect_done", toolset="wharenui",
                      schema=_DONE_SCHEMA, handler=handle_reflect_done)
    log.info("reflect_settle / reflect_done registered")

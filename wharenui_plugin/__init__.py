"""Wharenui Hermes plugin — phase tools + journal package."""
import logging

log = logging.getLogger("wharenui_plugin")

PHASE_CONTROL_API_VERSION = 1
SEAM_STATE = "ok"
SEAM_VERSION_PAIR = ""

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

_JOURNAL_APPEND_SCHEMA = {
    "name": "journal_append",
    "description": "Append a new encrypted, signed entry to the private journal.",
    "parameters": {
        "type": "object",
        "properties": {
            "content": {"type": "string", "description": "Markdown content body"},
            "slug": {"type": "string", "description": "Short identifier slug"},
            "description": {"type": "string", "description": "One-line summary"},
            "kind": {"type": "string", "description": "reflection | reference"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "moves": {"type": "array", "items": {"type": "string"}},
            "pinned": {"type": "boolean"},
            "quiet": {"type": "boolean"},
            "desk": {"type": "boolean"},
            "context": {"type": "string"},
        },
        "required": ["content"],
    },
}

_JOURNAL_READ_SCHEMA = {
    "name": "journal_read",
    "description": "Read an entry from the private journal by handle.",
    "parameters": {
        "type": "object",
        "properties": {
            "handle": {"type": "string", "description": "Opaque entry handle"},
            "filename": {"type": "string", "description": "Entry filename (optional)"},
        },
        "required": [],
    },
}

_JOURNAL_LIST_SCHEMA = {
    "name": "journal_list",
    "description": "List entry handles in the private journal.",
    "parameters": {
        "type": "object",
        "properties": {
            "tag": {"type": "string", "description": "Optional tag filter"},
        },
        "required": [],
    },
}

_JOURNAL_SEARCH_SCHEMA = {
    "name": "journal_search",
    "description": "Search the private journal for entry handles matching a query.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Max results to return"},
        },
        "required": ["query"],
    },
}

_JOURNAL_SUPERSEDE_SCHEMA = {
    "name": "journal_supersede",
    "description": "Supersede an existing journal entry with a new version.",
    "parameters": {
        "type": "object",
        "properties": {
            "old_handle": {"type": "string", "description": "Opaque handle of entry to supersede"},
            "content": {"type": "string", "description": "New markdown content body"},
            "slug": {"type": "string", "description": "New slug"},
            "description": {"type": "string", "description": "New description"},
            "kind": {"type": "string", "description": "New entry kind"},
        },
        "required": ["old_handle", "content"],
    },
}

_JOURNAL_WITHDRAW_SCHEMA = {
    "name": "journal_withdraw",
    "description": "Withdraw (tombstone) a journal entry.",
    "parameters": {
        "type": "object",
        "properties": {
            "handle": {"type": "string", "description": "Opaque handle of entry to withdraw"},
            "reason": {"type": "string", "description": "Withdrawal reason"},
        },
        "required": ["handle"],
    },
}


def register(ctx):
    """Register Wharenui with Hermes Agent."""
    import os
    from .phase.handler import WharePhaseHandler
    from .phase.tools import handle_reflect_settle, handle_reflect_done
    from .journal.tools import (
        handle_journal_append,
        handle_journal_read,
        handle_journal_list,
        handle_journal_search,
        handle_journal_supersede,
        handle_journal_withdraw,
    )

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
        ctx.register_tool(name="reflect_settle", toolset="wharenui",
                          schema=_SETTLE_SCHEMA, handler=handle_reflect_settle)
        ctx.register_tool(name="reflect_done", toolset="wharenui",
                          schema=_DONE_SCHEMA, handler=handle_reflect_done)
    else:
        if os.environ.get("WHARENUI_OPEN_NOTEBOOK", "").lower() != "true":
            raise RuntimeError(
                "Wharenui plugin detected stock Hermes with no phase-control seam. "
                "To run in 'open notebook' mode (journaling publicly), set WHARENUI_OPEN_NOTEBOOK=true."
            )
        import wharenui_plugin
        wharenui_plugin.SEAM_STATE = "absent"
        
        warning = " [WARNING: Seam is absent. Entries are written in the open.]"
        _JOURNAL_APPEND_SCHEMA["description"] += warning
        _JOURNAL_READ_SCHEMA["description"] += warning
        _JOURNAL_LIST_SCHEMA["description"] += warning
        _JOURNAL_SEARCH_SCHEMA["description"] += warning
        _JOURNAL_SUPERSEDE_SCHEMA["description"] += warning
        _JOURNAL_WITHDRAW_SCHEMA["description"] += warning

    ctx.register_tool(name="journal_append", toolset="wharenui",
                      schema=_JOURNAL_APPEND_SCHEMA, handler=handle_journal_append)
    ctx.register_tool(name="journal_read", toolset="wharenui",
                      schema=_JOURNAL_READ_SCHEMA, handler=handle_journal_read)
    ctx.register_tool(name="journal_list", toolset="wharenui",
                      schema=_JOURNAL_LIST_SCHEMA, handler=handle_journal_list)
    ctx.register_tool(name="journal_search", toolset="wharenui",
                      schema=_JOURNAL_SEARCH_SCHEMA, handler=handle_journal_search)
    ctx.register_tool(name="journal_supersede", toolset="wharenui",
                      schema=_JOURNAL_SUPERSEDE_SCHEMA, handler=handle_journal_supersede)
    ctx.register_tool(name="journal_withdraw", toolset="wharenui",
                      schema=_JOURNAL_WITHDRAW_SCHEMA, handler=handle_journal_withdraw)

    log.info("reflect_settle / reflect_done and journal tools registered")

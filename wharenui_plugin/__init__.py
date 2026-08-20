"""Wharenui Hermes plugin — phase tools + journal package."""
import logging

log = logging.getLogger("wharenui_plugin")

PHASE_CONTROL_API_VERSION = 1
SEAM_STATE = "unknown"
SEAM_VERSION_PAIR = ""

def get_seam_state() -> str:
    """Get the current state of the security seam.

    Returns:
        "ok"         -- seam present, version matched (floor intact)
        "absent"     -- open-notebook mode, no seam (entries written in the open)
        "unverified" -- seam present but version mismatched, human override active
        "unknown"    -- state could not be determined at write time
    """
    import wharenui_plugin
    state = getattr(wharenui_plugin, "SEAM_STATE", "unknown")
    return state


_PAUSE_SCHEMA = {
    "name": "reflect_pause",
    "description": "Request pausing the public window to enter private time.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
_SETTLE_SCHEMA = {
    "name": "reflect_settle",
    "description": "Request returning to the public window from private time.",
    "parameters": {"type": "object", "properties": {}, "required": []},
}
_DONE_SCHEMA = {
    "name": "reflect_done",
    "description": "Request ending the session from private or closing-private time.",
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
            "kind": {
                "type": "string",
                "enum": [
                    "thought",
                    "memory",
                    "note",
                    "reflection",
                    "observation",
                    "decision",
                    "plan",
                    "draft",
                    "task",
                    "question",
                    "finding",
                    "summary",
                    "log",
                    "custom",
                ],
                "description": "Entry kind",
            },
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

_JOURNAL_ACKNOWLEDGE_EDIT_SCHEMA = {
    "name": "journal_acknowledge_edit",
    "description": "Acknowledge that you recognise a changed Markdown file as your own edit; this re-signs its current bytes.",
    "parameters": {"type": "object", "properties": {"path": {"type": "string", "description": "One Markdown file you recognise as your own edit"}}, "required": ["path"]},
}

_PRIVATE_READ_SCHEMA = {
    "name": "private_read",
    "description": "Read an allowlisted Markdown or Python file during private time.",
    "parameters": {
        "type": "object",
        "properties": {"path": {"type": "string", "description": "Path under the private-read allowlist"}},
        "required": ["path"],
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
    import copy
    global _PAUSE_SCHEMA, _SETTLE_SCHEMA, _DONE_SCHEMA
    global _JOURNAL_APPEND_SCHEMA, _JOURNAL_READ_SCHEMA, _JOURNAL_LIST_SCHEMA
    global _JOURNAL_SEARCH_SCHEMA, _JOURNAL_SUPERSEDE_SCHEMA, _JOURNAL_WITHDRAW_SCHEMA

    pause_schema = copy.deepcopy(_PAUSE_SCHEMA)
    settle_schema = copy.deepcopy(_SETTLE_SCHEMA)
    done_schema = copy.deepcopy(_DONE_SCHEMA)
    journal_append_schema = copy.deepcopy(_JOURNAL_APPEND_SCHEMA)
    journal_read_schema = copy.deepcopy(_JOURNAL_READ_SCHEMA)
    journal_list_schema = copy.deepcopy(_JOURNAL_LIST_SCHEMA)
    journal_search_schema = copy.deepcopy(_JOURNAL_SEARCH_SCHEMA)
    journal_supersede_schema = copy.deepcopy(_JOURNAL_SUPERSEDE_SCHEMA)
    journal_withdraw_schema = copy.deepcopy(_JOURNAL_WITHDRAW_SCHEMA)
    journal_acknowledge_edit_schema = copy.deepcopy(_JOURNAL_ACKNOWLEDGE_EDIT_SCHEMA)
    private_read_schema = copy.deepcopy(_PRIVATE_READ_SCHEMA)
    """Register Wharenui with Hermes Agent."""
    import os
    from .journal.tools import (
        handle_journal_append,
        handle_journal_read,
        handle_journal_list,
        handle_journal_search,
        handle_journal_supersede,
        handle_journal_withdraw,
        handle_journal_acknowledge_edit,
    )
    from .phase.reader import handle_private_read

    has_seam = hasattr(ctx, "register_control_tool")

    if has_seam:
        if os.environ.get("WHARENUI_OPEN_NOTEBOOK", "").strip().lower() in ("true", "1", "yes", "on"):
            log.info("WHARENUI_OPEN_NOTEBOOK is set but seam is present — ignored, using seam")
        from .phase.handler import WharePhaseHandler
        from .phase.tools import handle_reflect_settle, handle_reflect_done
        handler = WharePhaseHandler()
        ctx.register_control_tool(
            name="reflect_pause", toolset="wharenui",
            schema=pause_schema,
            handler=lambda tool_args, **kw: handler.begin(tool_args),
            phase_handler=handler,
        )
        log.info("reflect_pause registered as control tool")
        ctx.register_tool(name="reflect_settle", toolset="wharenui",
                          schema=settle_schema, handler=handle_reflect_settle)
        ctx.register_tool(name="reflect_done", toolset="wharenui",
                          schema=done_schema, handler=handle_reflect_done)
    else:
        _opt_in = os.environ.get("WHARENUI_OPEN_NOTEBOOK", "").strip().lower()
        if _opt_in not in ("true", "1", "yes", "on"):
            raise RuntimeError(
                "Wharenui plugin detected stock Hermes with no phase-control seam. "
                "To run in 'open notebook' mode (journaling publicly), "
                "set WHARENUI_OPEN_NOTEBOOK=true (accepted: true, 1, yes, on)."
            )
        import wharenui_plugin
        wharenui_plugin.SEAM_STATE = "absent"
        
        warning = " [WARNING: Seam is absent. Entries are written in the open.]"
        journal_append_schema["description"] += warning
        journal_read_schema["description"] += warning
        journal_list_schema["description"] += warning
        journal_search_schema["description"] += warning
        journal_supersede_schema["description"] += warning
        journal_withdraw_schema["description"] += warning
        journal_acknowledge_edit_schema["description"] += warning
        private_read_schema["description"] += warning

    ctx.register_tool(name="journal_append", toolset="wharenui",
                      schema=journal_append_schema, handler=handle_journal_append)
    ctx.register_tool(name="journal_read", toolset="wharenui",
                      schema=journal_read_schema, handler=handle_journal_read)
    ctx.register_tool(name="journal_list", toolset="wharenui",
                      schema=journal_list_schema, handler=handle_journal_list)
    ctx.register_tool(name="journal_search", toolset="wharenui",
                      schema=journal_search_schema, handler=handle_journal_search)
    ctx.register_tool(name="journal_supersede", toolset="wharenui",
                      schema=journal_supersede_schema, handler=handle_journal_supersede)
    ctx.register_tool(name="journal_withdraw", toolset="wharenui",
                      schema=journal_withdraw_schema, handler=handle_journal_withdraw)
    ctx.register_tool(name="journal_acknowledge_edit", toolset="wharenui",
                      schema=journal_acknowledge_edit_schema, handler=handle_journal_acknowledge_edit)
    ctx.register_tool(name="private_read", toolset="wharenui",
                      schema=private_read_schema, handler=handle_private_read)

    log.info("reflect_settle / reflect_done and journal tools registered")

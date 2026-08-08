"""Phase-scoped toolset filter — public vs private."""
_PUBLIC_ONLY = {"reflect_pause"}
PRIVATE_ALLOWLIST = {
    "reflect_settle",
    "reflect_done",
    "journal_append",
    "journal_read",
    "journal_list",
    "journal_search",
    "journal_supersede",
    "journal_withdraw",
    "journal_acknowledge_edit",
}

def public_tools(all_tools):
    return [t for t in all_tools
            if (t.get("function", {}) or {}).get("name") not in PRIVATE_ALLOWLIST]

def private_tools(all_tools):
    return [t for t in all_tools
            if (t.get("function", {}) or {}).get("name") in PRIVATE_ALLOWLIST]

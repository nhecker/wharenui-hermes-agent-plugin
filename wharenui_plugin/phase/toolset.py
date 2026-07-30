"""Phase-scoped toolset filter — public vs private."""
_PUBLIC_ONLY = {"reflect_pause"}
_PRIVATE_ONLY = {"reflect_settle", "reflect_done"}

def public_tools(all_tools):
    return [t for t in all_tools
            if (t.get("function", {}) or {}).get("name") not in _PRIVATE_ONLY]

def private_tools(all_tools):
    return [t for t in all_tools
            if (t.get("function", {}) or {}).get("name") not in _PUBLIC_ONLY]

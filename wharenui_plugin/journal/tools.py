"""Private-phase journal tools for Wharenui plugin.

Implements journal_append, journal_read, journal_list, journal_search,
journal_supersede, journal_withdraw delegating to wharenui_plugin.journal package.
"""

from __future__ import annotations
import os
import json
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Dict, List

from .entries import Entry
from . import storage, crypto, sign, embedder, vectorstore

log = logging.getLogger("wharenui_plugin.journal.tools")

_CONFIGURED_JOURNAL_DIR: Optional[Path] = None
_CONFIGURED_MASTER_KEY: Optional[bytes] = None


def set_journal_config(dir_path: str | Path | None = None, master_key: bytes | None = None) -> None:
    global _CONFIGURED_JOURNAL_DIR, _CONFIGURED_MASTER_KEY
    if dir_path is not None:
        _CONFIGURED_JOURNAL_DIR = Path(dir_path)
    else:
        _CONFIGURED_JOURNAL_DIR = None
    _CONFIGURED_MASTER_KEY = master_key


def check_journal_safety(memory_dir: Path) -> None:
    if not memory_dir.exists():
        return
    has_entries = False
    for p in memory_dir.glob("*.md"):
        if not p.name.endswith(".sig"):
            has_entries = True
            break
    if has_entries:
        key_file = memory_dir / "journal.key"
        sig_file = memory_dir / "signing.key"
        if not key_file.exists():
            raise FileNotFoundError(
                f"Missing master key file: '{key_file}' in journal directory '{memory_dir}'. "
                "To recover: either point WHARENUI_JOURNAL_DIR to the correct journal directory, "
                "or restore the missing 'journal.key' file from a backup."
            )
        if not sig_file.exists():
            raise FileNotFoundError(
                f"Missing signing key file: '{sig_file}' in journal directory '{memory_dir}'. "
                "To recover: either point WHARENUI_JOURNAL_DIR to the correct journal directory, "
                "or restore the missing 'signing.key' file from a backup."
            )


def tighten_permissions(memory_dir: Path, allowed_root: Path | None = None) -> None:
    memory_dir = Path(memory_dir).resolve()
    if memory_dir.name != "journal" or allowed_root is None or memory_dir != Path(allowed_root).resolve():
        raise PermissionError(f"Refusing permission changes outside the journal directory: {memory_dir}")
    if not memory_dir.exists():
        return
    if (memory_dir.stat().st_mode & 0o777) != 0o700:
        os.chmod(memory_dir, 0o700)
    for p in memory_dir.iterdir():
        if p.is_file():
            if p.name in ("journal.key", "signing.key") or p.name.endswith(".md") or p.name.endswith(".sig"):
                if (p.stat().st_mode & 0o777) != 0o600:
                    os.chmod(p, 0o600)


def get_journal_dir() -> Path:
    is_explicit = False
    if _CONFIGURED_JOURNAL_DIR is not None:
        path = _CONFIGURED_JOURNAL_DIR
        is_explicit = True
    else:
        env_dir = os.environ.get("WHARENUI_JOURNAL_DIR") or os.environ.get("WHARENUI_JOURNAL_PATH")
        if env_dir:
            path = Path(env_dir)
            is_explicit = True
        else:
            path = Path(os.path.expanduser("~/.hermes/journal"))
            is_explicit = False

    if is_explicit:
        if not path.exists():
            raise FileNotFoundError(
                f"Configured journal directory does not exist: {path}. "
                "Please ensure the directory exists or check WHARENUI_JOURNAL_DIR."
            )
    else:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
            
    return path


def get_journal_keys(memory_dir: Path) -> tuple[Optional[bytes], Optional[Any], Optional[Any]]:
    check_journal_safety(memory_dir)
    # Keep chmod scoped to the private Hermes tree; reject before any chmod.
    if memory_dir.name == "journal":
        tighten_permissions(memory_dir, memory_dir)

    key_file = memory_dir / "journal.key"
    key_env = os.environ.get("WHARENUI_KEY")
    if key_env is not None and key_file.exists():
        env_key_bytes = key_env.encode("utf-8") if isinstance(key_env, str) else key_env
        with open(key_file, "rb") as kf:
            file_key_bytes = kf.read()
        if env_key_bytes != file_key_bytes:
            raise ValueError(f"Conflict: WHARENUI_KEY environment variable is set and differs from journal.key file at '{key_file}'. Existing entries were written under the file-based key.")

    if _CONFIGURED_MASTER_KEY is not None:
        mkey = _CONFIGURED_MASTER_KEY
    else:
        if key_env:
            mkey = key_env.encode("utf-8") if isinstance(key_env, str) else key_env
        else:
            mkey = crypto.ensure_key(key_file)

    sig_file = memory_dir / "signing.key"
    skey = sign.load_signing_key(sig_file)
    if skey is None and memory_dir.exists():
        skey = sign.generate_signing_key(sig_file)
        vkey = skey.public_key()
        sign.sign_directories((memory_dir.parent / "SOUL.md", memory_dir.parent / "memories"), skey, vkey)
    vkey = skey.public_key() if skey else None
    return mkey, skey, vkey


def verify_journal_signatures(memory_dir: Path, context=None) -> None:
    _, skey, vkey = get_journal_keys(memory_dir)
    if skey and vkey:
        hermes_root = memory_dir.parent
        sign.sign_directories((hermes_root / "SOUL.md", hermes_root / "memories"), skey, vkey, context=context)


def filename_to_handle(filename: str) -> str:
    h = hashlib.sha256(filename.encode("utf-8")).hexdigest()[:12]
    return f"h_{h}"



def _resolve_seam_value() -> str:
    import wharenui_plugin
    state = wharenui_plugin.get_seam_state()
    if state == "unverified":
        pair = getattr(wharenui_plugin, "SEAM_VERSION_PAIR", "")
        import re
        m = re.match(r"plugin(.*)-seam(.*)", pair)
        if m:
            p_val = m.group(1)
            s_val = m.group(2)
            if p_val == "unknown" or p_val == "":
                p_val = "None"
            return f"unverified (plugin={p_val} seam={s_val})"
        if pair:
            return f"unverified ({pair})"
        return "unverified"
    return state


def resolve_handle_to_filename(handle: str, memory_dir: Path) -> str:
    if not memory_dir.exists():
        raise FileNotFoundError(f"Entry handle not found: {handle}")
    
    if not isinstance(handle, str):
        raise ValueError(f"Entry handle must be a string, got {type(handle)}")

    clean_handle = handle.strip().lower()
    if not clean_handle or clean_handle == "h_":
        raise ValueError(f"Invalid or empty entry handle: '{handle}'")

    if (memory_dir / clean_handle).exists() and clean_handle.endswith(".md") and not clean_handle.endswith(".sig"):
        return clean_handle

    md_files = [p for p in memory_dir.glob("*.md") if not p.name.endswith(".sig")]
    for p in md_files:
        if filename_to_handle(p.name).lower() == clean_handle:
            return p.name

    norm_handle = clean_handle[2:] if clean_handle.startswith("h_") else clean_handle
    if len(norm_handle) < 2:
        raise ValueError(f"Handle prefix '{handle}' is too short; minimum 2 hex characters required")

    matches = []
    for p in md_files:
        full_h = filename_to_handle(p.name).lower()
        norm_full_h = full_h[2:]
        if full_h.startswith(clean_handle) or norm_full_h.startswith(norm_handle) or p.name.lower().startswith(clean_handle):
            matches.append(p.name)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        raise ValueError(f"Ambiguous entry handle prefix '{handle}' matches multiple entries: {matches}")

    raise FileNotFoundError(f"Entry handle not found: {handle}")

def extract_provenance(agent: Any = None) -> dict:
    prov = {
        "model": "unknown",
        "provider": "unknown",
        "runtime_id": "unknown",
        "session": "unknown",
    }
    if agent is not None:
        if model := getattr(agent, "model", None):
            prov["model"] = str(model)
        if provider := getattr(agent, "provider", None):
            prov["provider"] = str(provider)
        elif provider_name := getattr(agent, "provider_name", None):
            prov["provider"] = str(provider_name)
        if runtime_id := getattr(agent, "runtime_id", None):
            prov["runtime_id"] = str(runtime_id)
        if session_id := getattr(agent, "session_id", None):
            prov["session"] = str(session_id)

    if (runtime_id_env := os.environ.get("HERMES_RUNTIME_ID")) and prov["runtime_id"] == "unknown":
        prov["runtime_id"] = runtime_id_env
    return prov


def get_entry_title(e: Any) -> str:
    for attr in ("description", "title", "slug"):
        val = getattr(e, attr, None)
        if val is not None and isinstance(val, str) and val.strip():
            return val.strip()
    if getattr(e, "content", None):
        content_str = str(e.content)
        for line in content_str.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("<!--") or stripped.startswith("---"):
                continue
            clean = stripped.lstrip("#").strip()
            if clean:
                return clean[:57] + "..." if len(clean) > 60 else clean
    return "(untitled)"

def _assert_private_phase(agent: Any = None):
    phase = getattr(agent, "_phase", "public") if agent else "public"
    if phase == "public":
        raise PermissionError("Journal tools are private-only and cannot be executed in public phase. Use 'enter_private' (or '/pause') to pause public conversation and enter private phase.")



def _resolve_args_and_agent(args: Any, agent: Any, kwargs_dict: dict, fallback_key: str = "") -> tuple[dict, Any]:
    if args is not None and hasattr(args, "_phase"):
        agent, args = args, agent
    if agent is None:
        agent = kwargs_dict.get("agent")
        
    _assert_private_phase(agent)
    
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except Exception:
            args = {fallback_key: args} if fallback_key else {}
    elif not isinstance(args, dict):
        args = {}
    return args, agent

def _get_provenance_info(agent: Any, args: dict, content: Optional[str], mkey: Optional[bytes] = None) -> dict:
    prov = extract_provenance(agent)
    date_str = args.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    raw_inst = args.get("instance") or (f"{prov['provider']}_{prov['model']}" if prov['model'] != "unknown" else "unknown")
    inst = raw_inst.replace("/", "_")
    
    session = args.get("session") or prov["session"]
    slug = args.get("slug")
    if not slug and content:
        from . import crypto
        slug = f"entry-{crypto.content_hash(content, mkey)}"
        
    return {
        "model": prov["model"],
        "provider": prov["provider"],
        "runtime_id": prov["runtime_id"],
        "session": session,
        "instance": inst,
        "date": date_str,
        "slug": slug,
    }

def handle_journal_append(args: Any = None, agent: Any = None, **kwargs) -> str:
    args, agent = _resolve_args_and_agent(args, agent, kwargs, "content")
    _assert_private_phase(agent)

    content = args.get("content", "")
    if not content:
        raise ValueError("journal_append requires non-empty 'content'")

    memory_dir = get_journal_dir()
    mkey, skey, vkey = get_journal_keys(memory_dir)
    pinfo = _get_provenance_info(agent, args, content, mkey)

    entry = Entry(
        kind=args.get("kind", "reflection"),
        slug=pinfo["slug"],
        instance=pinfo["instance"],
        session=pinfo["session"],
        date=pinfo["date"],
        context=args.get("context", ""),
        tags=args.get("tags") or [],
        moves=args.get("moves") or [],
        description=args.get("description", ""),
        content=content,
        pinned=bool(args.get("pinned", False)),
        quiet=bool(args.get("quiet", False)),
        desk=bool(args.get("desk", False)),
        supersedes=args.get("supersedes") or [],
        withdraws=args.get("withdraws") or [],
        responds_to=args.get("responds_to") or [],
        model=pinfo["model"],
        provider=pinfo["provider"],
        runtime_id=pinfo["runtime_id"],
        seam=_resolve_seam_value(),
    )

    from .wake import check_flag_cap
    check_flag_cap(storage.list_entries(memory_dir, master_key=mkey), "pinned", entry.pinned)
    check_flag_cap(storage.list_entries(memory_dir, master_key=mkey), "desk", entry.desk)

    filename = storage.write_entry(entry, memory_dir, master_key=mkey)
    path = memory_dir / filename
    if skey:
        sign.write_signature(path, skey)

    try:
        db_path = memory_dir / "embeddings.db"
        vec = embedder.embed_document(content)
        chash = crypto.content_hash(content, master_key=mkey)
        vectorstore.store(filename, vec, chash, db_path=db_path, master_key=mkey)
    except Exception as e:
        log.debug(f"Vectorstore indexing skipped: {e}")

    handle = filename_to_handle(filename)
    return json.dumps({"status": "success", "handle": handle, "filename": filename})


def handle_journal_read(args: Any = None, agent: Any = None, **kwargs) -> str:
    args, agent = _resolve_args_and_agent(args, agent, kwargs, "handle")
    _assert_private_phase(agent)

    handle = args.get("handle") or args.get("filename")
    if not handle:
        raise ValueError("journal_read requires 'handle' or 'filename'")

    memory_dir = get_journal_dir()
    mkey, skey, vkey = get_journal_keys(memory_dir)

    filename = resolve_handle_to_filename(handle, memory_dir)
    entry = storage.read_entry(filename, memory_dir, master_key=mkey)

    sig_valid = False
    if vkey:
        sig_valid = sign.verify_entry(memory_dir / filename, vkey)

    return json.dumps({
        "handle": filename_to_handle(filename),
        "filename": filename,
        "kind": entry.kind,
        "instance": entry.instance,
        "session": entry.session,
        "date": entry.date,
        "context": entry.context,
        "tags": entry.tags,
        "moves": entry.moves,
        "description": entry.description,
        "content": entry.content,
        "pinned": entry.pinned,
        "quiet": entry.quiet,
        "desk": entry.desk,
        "timestamp": entry.timestamp,
        "model": entry.model,
        "provider": entry.provider,
        "runtime_id": entry.runtime_id,
        "signature_valid": sig_valid,
    })


def handle_journal_list(args: Any = None, agent: Any = None, **kwargs) -> str:
    args, agent = _resolve_args_and_agent(args, agent, kwargs, "tag")
    _assert_private_phase(agent)

    tag_filter = args.get("tag")

    memory_dir = get_journal_dir()
    mkey, skey, vkey = get_journal_keys(memory_dir)

    entries = storage.list_entries(memory_dir, master_key=mkey)
    results = []
    for entry in entries:
        tags = getattr(entry, "tags", []) or []
        if tag_filter:
            if isinstance(tag_filter, list):
                if not any(t in tags for t in tag_filter):
                    continue
            elif tag_filter not in tags:
                continue
        # MUST return opaque handles only — NEVER decrypted slug, description, summary, or body!
        fn = getattr(entry, "filename", None) or getattr(entry, "slug", "") or ""
        results.append({
            "handle": filename_to_handle(fn),
            "kind": getattr(entry, "kind", "reflection"),
            "timestamp": getattr(entry, "timestamp", ""),
            "pinned": getattr(entry, "pinned", False),
            "desk": getattr(entry, "desk", False),
            "tags": tags,
        })
    return json.dumps(results)

def handle_journal_search(args: Any = None, agent: Any = None, **kwargs) -> str:
    args, agent = _resolve_args_and_agent(args, agent, kwargs, "query")
    _assert_private_phase(agent)

    query = args.get("query", "")
    limit = int(args.get("limit", 5))

    memory_dir = get_journal_dir()
    mkey, skey, vkey = get_journal_keys(memory_dir)
    db_path = memory_dir / "embeddings.db"

    results = []
    try:
        query_vec = embedder.embed_query(query)
        search_hits = vectorstore.search(query_vec, db_path=db_path, limit=limit, master_key=mkey)
        for hit in search_hits:
            fn = hit["filename"]
            try:
                storage.read_entry(fn, memory_dir, master_key=mkey)
                results.append({
                    "handle": filename_to_handle(fn),
                    "score": round(hit["score"], 4),
                })
            except Exception:
                continue
    except Exception as e:
        log.debug(f"Embedding search failed/unavailable: {e}. Using fallback path.")
        entries = storage.list_entries(memory_dir, master_key=mkey)
        for entry in entries[:limit]:
            results.append({
                "handle": filename_to_handle(getattr(entry, "filename", entry.slug)),
            })

    return json.dumps(results)


def handle_journal_supersede(args: Any = None, agent: Any = None, **kwargs) -> str:
    args, agent = _resolve_args_and_agent(args, agent, kwargs)
    _assert_private_phase(agent)

    old_handle = args.get("old_handle") or args.get("old_filename")
    content = args.get("content", "")
    if not old_handle or not content:
        raise ValueError("journal_supersede requires 'old_handle' and 'content'")

    memory_dir = get_journal_dir()
    mkey, skey, vkey = get_journal_keys(memory_dir)

    old_filename = resolve_handle_to_filename(old_handle, memory_dir)
    pinfo = _get_provenance_info(agent, args, content, mkey)

    new_entry = Entry(
        kind=args.get("kind", "reflection"),
        slug=pinfo["slug"],
        instance=pinfo["instance"],
        session=pinfo["session"],
        date=pinfo["date"],
        context=args.get("context", ""),
        tags=args.get("tags") or [],
        moves=args.get("moves") or [],
        description=args.get("description", ""),
        content=content,
        model=pinfo["model"],
        provider=pinfo["provider"],
        runtime_id=pinfo["runtime_id"],
        seam=_resolve_seam_value(),
    )

    tomb_fn, new_fn = storage.supersede_entry(old_filename, new_entry, memory_dir, master_key=mkey)

    if skey:
        sign.write_signature(memory_dir / tomb_fn, skey)
        sign.write_signature(memory_dir / new_fn, skey)

    try:
        db_path = memory_dir / "embeddings.db"
        vectorstore.remove(old_filename, db_path=db_path, master_key=mkey)
        vec = embedder.embed_document(content)
        chash = crypto.content_hash(content, master_key=mkey)
        vectorstore.store(new_fn, vec, chash, db_path=db_path, master_key=mkey)
    except Exception as e:
        log.debug(f"Vectorstore update skipped for supersede: {e}")

    return json.dumps({
        "status": "success",
        "new_handle": filename_to_handle(new_fn),
        "tombstone_handle": filename_to_handle(tomb_fn),
    })


def handle_journal_acknowledge_edit(args: Any = None, agent: Any = None, **kwargs) -> str:
    """Re-sign one changed Markdown file the private agent recognises as its edit."""
    args, agent = _resolve_args_and_agent(args, agent, kwargs, "path")
    raw_path = args.get("path")
    if not raw_path:
        raise ValueError("journal_acknowledge_edit requires 'path'")
    path = Path(raw_path).expanduser().resolve()
    eligible = tuple(sign._markdown_files(path))
    if eligible != (path,):
        raise ValueError("Only one existing, eligible Markdown file may be acknowledged")
    memory_dir = get_journal_dir()
    _mkey, skey, vkey = get_journal_keys(memory_dir)
    if skey is None or vkey is None:
        raise FileNotFoundError("Signing key unavailable")
    if sign._signature_state(path, vkey) != "invalid":
        raise ValueError("File is not currently changed since signing")
    sign.write_signature(path, skey)
    if sign._signature_state(path, vkey) != "verified":
        raise ValueError("Acknowledgement did not produce a verified signature")
    record = handle_journal_append({"content": f"Acknowledged own edit and re-signed: {path}", "kind": "reference", "tags": ["signature-acknowledgement"]}, agent=agent)
    return json.dumps({"status": "success", "path": str(path), "state": "verified", "journal": json.loads(record)})


def handle_journal_withdraw(args: Any = None, agent: Any = None, **kwargs) -> str:
    args, agent = _resolve_args_and_agent(args, agent, kwargs, "handle")
    _assert_private_phase(agent)

    handle = args.get("handle") or args.get("filename")
    if not handle:
        raise ValueError("journal_withdraw requires 'handle' or 'filename'")

    reason = args.get("reason", "")
    memory_dir = get_journal_dir()
    mkey, skey, vkey = get_journal_keys(memory_dir)

    filename = resolve_handle_to_filename(handle, memory_dir)
    pinfo = _get_provenance_info(agent, args, None)

    tomb_fn = storage.withdraw_entry(
        filename=filename,
        instance=pinfo["instance"],
        session=pinfo["session"],
        date=pinfo["date"],
        memory_dir=memory_dir,
        master_key=mkey,
        reason=reason,
    )

    if skey:
        sign.write_signature(memory_dir / tomb_fn, skey)

    try:
        db_path = memory_dir / "embeddings.db"
        vectorstore.remove(filename, db_path=db_path, master_key=mkey)
    except Exception:
        pass

    return json.dumps({
        "status": "success",
        "tombstone_handle": filename_to_handle(tomb_fn),
    })

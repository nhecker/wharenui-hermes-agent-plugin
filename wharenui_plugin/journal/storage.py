"""Storage layer for Wharenui journal.

Plain markdown files with YAML frontmatter. One file per entry.
Encrypted at rest when a key is available. Delete is append-only
via tombstone entries — never hard-unlink.

Decoupled from any framework config: accepts memory_dir and
key_material explicitly.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import crypto
from cryptography.fernet import InvalidToken
from .entries import Entry, make_tombstone


FRONTMATTER_DELIM = "---"

# Withdrawn and superseded entries are renamed to <token>.tomb.md so that
# eligibility checks (read/list/search) can skip them by filename instead of
# decrypting every entry. The sig path is already canonical (derived from the
# leading token via split(".")[0]), so no sig file needs to move.
TOMB_SUFFIX = ".tomb"

# When a key is unavailable, encryption is off and files are plaintext.
# This is the relaxed mode — the design calls for encryption always-on
# in production, but the journal package tolerates no-key for testing
# and degraded operation.


def _get_stem(name: str) -> str:
    return name.split(".")[0]


def _read_file_content(path: Path, master_key: Optional[bytes] = None) -> str:
    """Read a file, decrypting if encrypted.

    Tries per-entry derived key first (v2), falls back to master
    key (v1) for entries encrypted before key derivation was added.
    Plaintext files are read directly.
    """
    raw = path.read_bytes()
    if crypto.is_encrypted(raw):
        if master_key:
            # 1. Try deriving from stem (new style)
            try:
                stem = _get_stem(path.name)
                entry_key = crypto.derive_key(stem, master_key)
                return crypto.decrypt(raw, entry_key).replace("\r\n", "\n")
            except InvalidToken:
                pass
            # 2. Try deriving from literal filename (old style)
            try:
                entry_key = crypto.derive_key(path.name, master_key)
                return crypto.decrypt(raw, entry_key).replace("\r\n", "\n")
            except InvalidToken:
                pass
            # 3. Fall back to master key directly (very old style)
            try:
                return crypto.decrypt(raw, master_key).replace("\r\n", "\n")
            except InvalidToken:
                pass
        raise ValueError("Failed to decrypt entry: key mismatched or corrupted")
    else:
        text = raw.decode("utf-8")
    return text.replace("\r\n", "\n")


def _write_file_content(
    path: Path, text: str, master_key: Optional[bytes] = None
) -> None:
    """Write a file, encrypting with per-entry derived key if available."""
    if master_key:
        stem = _get_stem(path.name)
        entry_key = crypto.derive_key(stem, master_key)
        path.write_bytes(crypto.encrypt(text, entry_key))
    else:
        path.write_text(text, encoding="utf-8")
    import os
    os.chmod(path, 0o600)


def _format_frontmatter(entry: Entry) -> str:
    """Format an Entry into YAML frontmatter + content string."""
    lines = [
        FRONTMATTER_DELIM,
        f"kind: {entry.kind}",
        f"slug: {entry.slug}",
        f"instance: {entry.instance}",
        f"session: {entry.session}",
        f"date: {entry.date}",
        f"context: {entry.context}",
        f"tags: [{', '.join(entry.tags)}]",
        f"moves: [{', '.join(entry.moves)}]",
    ]
    if entry.timestamp:
        lines.append(f"timestamp: {entry.timestamp}")
    if entry.description:
        lines.append(f"description: {entry.description}")
    if entry.pinned:
        lines.append("pinned: true")
    if entry.quiet:
        lines.append("quiet: true")
    if entry.desk:
        lines.append("desk: true")
    if entry.supersedes:
        lines.append(f"supersedes: [{', '.join(entry.supersedes)}]")
    if entry.withdraws:
        lines.append(f"withdraws: [{', '.join(entry.withdraws)}]")
    if entry.responds_to:
        lines.append(f"responds_to: [{', '.join(entry.responds_to)}]")
    if entry.model:
        lines.append(f"model: {entry.model}")
    if entry.provider:
        lines.append(f"provider: {entry.provider}")
    if entry.runtime_id:
        lines.append(f"runtime_id: {entry.runtime_id}")
    if entry.seam is not None:
        lines.append(f"seam: {entry.seam}")
    lines.extend([FRONTMATTER_DELIM, "", entry.content])
    return "\n".join(lines) + "\n"


def _parse_frontmatter(text: str) -> dict:
    """Parse YAML-like frontmatter + content from entry text."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != FRONTMATTER_DELIM:
        raise ValueError("missing opening frontmatter delimiter")

    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == FRONTMATTER_DELIM:
            end_idx = i
            break
    if end_idx is None:
        raise ValueError("missing closing frontmatter delimiter")

    fm: dict = {}
    for line in lines[1:end_idx]:
        if not line.strip():
            continue
        key, _, value = line.partition(":")
        fm[key.strip()] = _parse_value(value.strip())

    # Skip one blank line after closing delim if present
    content_start = end_idx + 1
    if content_start < len(lines) and lines[content_start] == "":
        content_start += 1
    fm["content"] = "\n".join(lines[content_start:]).rstrip("\n")
    return fm


def _parse_value(s: str):
    """Parse a YAML-like value: string, list of strings, or boolean."""
    if s.startswith("[") and s.endswith("]"):
        inner = s[1:-1].strip()
        if not inner:
            return []
        return [x.strip() for x in inner.split(",")]
    if s.lower() == "true":
        return True
    if s.lower() == "false":
        return False
    return s


def _opaque_filename(entry: Entry, master_key: Optional[bytes] = None) -> str:
    """Build a filename using an opaque token instead of cleartext metadata."""
    identifying_material = f"{entry.session}_{entry.timestamp}_{entry.slug}"
    identifying_material = identifying_material.replace(":", "_")
    if master_key:
        import hmac
        h = hmac.new(master_key, identifying_material.encode("utf-8"), "sha256").hexdigest()
        return f"{h}.md"
    else:
        import hashlib
        h = hashlib.sha256(identifying_material.encode("utf-8")).hexdigest()
        return f"{h}.md"


def _entry_from_dict(d: dict, filename: str) -> Entry:
    """Convert a parsed frontmatter dict into an Entry."""
    entry = Entry(
        kind=d.get("kind", "reflection"),
        slug=d.get("slug") or filename,
        instance=d.get("instance", ""),
        session=d.get("session", ""),
        date=d.get("date", ""),
        context=d.get("context", ""),
        tags=d.get("tags", []),
        moves=d.get("moves", []),
        description=d.get("description", ""),
        content=d.get("content", ""),
        pinned=d.get("pinned", False),
        quiet=d.get("quiet", False),
        desk=d.get("desk", False),
        timestamp=d.get("timestamp", ""),
        supersedes=d.get("supersedes", []),
        withdraws=d.get("withdraws", []),
        responds_to=d.get("responds_to", []),
        model=d.get("model", "unknown"),
        provider=d.get("provider", "unknown"),
        runtime_id=d.get("runtime_id", "unknown"),
        seam=d.get("seam"),
    )
    entry.filename = filename
    return entry


# --- Public API ---


def write_entry(
    entry: Entry,
    memory_dir: Path,
    master_key: Optional[bytes] = None,
) -> str:
    """Write a journal entry. Returns the filename written.

    Encrypted at rest when master_key is provided.
    """
    memory_dir.mkdir(parents=True, exist_ok=True)
    if not entry.timestamp:
        entry.timestamp = datetime.now(timezone.utc).isoformat()
    if entry.seam is None:
        try:
            from .tools import _resolve_seam_value
            entry.seam = _resolve_seam_value()
        except (ImportError, AttributeError):
            try:
                import wharenui_plugin
                entry.seam = wharenui_plugin.get_seam_state()
            except (ImportError, AttributeError):
                entry.seam = "unknown"
    filename = _opaque_filename(entry, master_key)
    # Invariant: a GENERATED filename must be <dot-free-token>.md with nothing in between.
    # This survives python -O (ValueError, not AssertionError).
    # On-disk relabelled shapes like <token>.tomb.md are legal and remain readable and
    # verifiable (see _get_stem, _read_file_content, sign.signature_path_for) — they are
    # produced by _rename_to_tomb, never by this function.
    _token = filename.split(".")[0]
    if filename != f"{_token}.md":
        raise ValueError(
            f"Generated filename '{filename}' contains intermediate dots; "
            f"generated names must be <dot-free-token>.md"
        )
    path = memory_dir / filename
    _write_file_content(path, _format_frontmatter(entry), master_key)
    return filename


def _has_tomb_suffix(filename: str) -> bool:
    """Return True if the filename has the .tomb.md suffix convention."""
    token = filename.split(".")[0]
    return filename == f"{token}{TOMB_SUFFIX}.md"


def _rename_to_tomb(filename: str, memory_dir: Path) -> str:
    """Rename <token>.md to <token>.tomb.md. Returns the new filename.

    If the file is already suffixed or doesn't exist, returns the original name.
    The .sig file is NOT renamed — signature_path_for() already canonicalises to
    the leading token, so both <token>.md.sig and <token>.tomb.md.sig resolve to
    the same path.
    """
    if _has_tomb_suffix(filename):
        return filename
    old_path = memory_dir / filename
    if not old_path.exists():
        return filename
    token = filename.split(".")[0]
    new_filename = f"{token}{TOMB_SUFFIX}.md"
    new_path = memory_dir / new_filename
    if new_path.exists():
        raise FileExistsError(
            f"Refusing to clobber existing tombstone: {new_path} "
            f"(source: {old_path})"
        )
    old_path.rename(new_path)
    return new_filename


def _compute_legacy_tombstoned(
    memory_dir: Path, master_key: Optional[bytes] = None
) -> set[str]:
    """Single-pass scan: return filenames targeted by legacy frontmatter tombstones.

    Computed once per listing and threaded into _is_tombstoned so the per-entry
    scan is eliminated.  Only references found in supersedes/withdraws frontmatter
    are returned — suffix-renamed entries are handled by the fast path.
    """
    legacy: set[str] = set()
    for p in memory_dir.glob("*.md"):
        if p.suffix == ".sig":
            continue
        try:
            text = _read_file_content(p, master_key)
        except Exception:
            continue
        if "supersedes:" in text or "withdraws:" in text:
            parsed = _parse_frontmatter(text)
            for t in parsed.get("supersedes", []):
                legacy.add(t)
            for t in parsed.get("withdraws", []):
                legacy.add(t)
    return legacy


def _is_tombstoned(
    filename: str,
    memory_dir: Path,
    master_key: Optional[bytes] = None,
    legacy_tombstoned: Optional[set[str]] = None,
) -> bool:
    """Check if an entry has been tombstoned/superseded.

    Fast path: <token>.tomb.md suffix or a .tomb.md sibling exists.
    Slow path: if legacy_tombstoned is provided, check membership; otherwise
    fall back to a full decrypt-every-entry scan (standalone read_entry only).
    """
    if _has_tomb_suffix(filename):
        return True
    token = filename.split(".")[0]
    tomb_name = f"{token}{TOMB_SUFFIX}.md"
    if (memory_dir / tomb_name).exists():
        return True

    if legacy_tombstoned is not None:
        return filename in legacy_tombstoned

    for p in memory_dir.glob("*.md"):
        if p.name == filename or p.suffix == ".sig":
            continue
        try:
            text = _read_file_content(p, master_key)
        except Exception:
            continue
        if "supersedes:" in text or "withdraws:" in text:
            parsed = _parse_frontmatter(text)
            if filename in parsed.get("supersedes", []) or filename in parsed.get(
                "withdraws", []
            ):
                return True
    return False


def read_entry(
    filename: str,
    memory_dir: Path,
    master_key: Optional[bytes] = None,
    include_tombstoned: bool = False,
    legacy_tombstoned: Optional[set[str]] = None,
) -> Entry:
    """Read an entry from disk. Returns an Entry.

    Raises FileNotFoundError if the file is missing or the entry has been
    tombstoned/withdrawn. Raises ValueError if frontmatter is malformed.
    """
    path = memory_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"No entry: {filename}")
    text = _read_file_content(path, master_key)
    parsed = _parse_frontmatter(text)
    entry = _entry_from_dict(parsed, filename)
    if not include_tombstoned:
        if entry.kind == "tombstone":
            raise FileNotFoundError(f"Entry {filename} has been tombstoned")
        if _has_tomb_suffix(filename):
            raise FileNotFoundError(f"Entry {filename} has been withdrawn (filename suffix)")
        if _is_tombstoned(filename, memory_dir, master_key, legacy_tombstoned):
            raise FileNotFoundError(f"Entry {filename} has been tombstoned/superseded")
    return entry


def list_entries(
    memory_dir: Path,
    master_key: Optional[bytes] = None,
    include_tombstoned: bool = False,
) -> list[Entry]:
    """List all entries in the journal directory.

    By default, tombstoned entries are excluded. Set include_tombstoned=True
    to include them (for maintenance/audit).
    """
    memory_dir = Path(memory_dir)
    if not memory_dir.exists():
        return []
    if include_tombstoned:
        # Simple path: read everything, no tombstone filtering
        entries = []
        for path in memory_dir.glob("*.md"):
            if path.suffix == ".sig":
                continue
            try:
                entry = read_entry(
                    path.name, memory_dir, master_key, include_tombstoned
                )
            except (ValueError, FileNotFoundError):
                continue
            entries.append(entry)
        entries.sort(key=lambda e: (e.timestamp or "", e.date or "", e.slug or ""))
        return entries

    # Filtering path: one pass to read + build legacy set, second pass to filter.
    # Each file is decrypted exactly once.
    raw_entries: list[tuple[Entry, str]] = []
    legacy_tombstoned: set[str] = set()
    for path in memory_dir.glob("*.md"):
        if path.suffix == ".sig":
            continue
        try:
            text = _read_file_content(path, master_key)
        except (ValueError, FileNotFoundError):
            continue
        try:
            parsed = _parse_frontmatter(text)
        except ValueError:
            continue
        entry = _entry_from_dict(parsed, path.name)
        # Collect legacy tombstone targets from frontmatter
        if "supersedes:" in text or "withdraws:" in text:
            for t in parsed.get("supersedes", []):
                legacy_tombstoned.add(t)
            for t in parsed.get("withdraws", []):
                legacy_tombstoned.add(t)
        raw_entries.append((entry, path.name))

    entries = []
    for entry, fn in raw_entries:
        if entry.kind == "tombstone":
            continue
        if _has_tomb_suffix(fn):
            continue
        if fn in legacy_tombstoned:
            continue
        entries.append(entry)
    entries.sort(key=lambda e: (e.timestamp or "", e.date or "", e.slug or ""))
    return entries


def supersede_entry(
    old_filename: str,
    new_entry: Entry,
    memory_dir: Path,
    master_key: Optional[bytes] = None,
) -> tuple[str, str]:
    """Replace an entry with a new version.

    Writes a tombstone for the old entry, then writes the new entry
    with a supersedes reference. Both entries remain on disk.
    Returns (tombstone_filename, new_filename).
    """
    old_path = memory_dir / old_filename
    if not old_path.exists():
        raise FileNotFoundError(f"No entry to supersede: {old_filename}")

    # Tombstone the old entry
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    tombstone = make_tombstone(
        target=old_filename,
        instance=new_entry.instance,
        session=new_entry.session,
        date=date_str,
        reason=f"Superseded by {new_entry.slug}",
    )
    tomb_fn = write_entry(tombstone, memory_dir, master_key)

    # Write the new entry with supersedes reference
    new_entry.supersedes = list(set(new_entry.supersedes + [old_filename]))
    new_fn = write_entry(new_entry, memory_dir, master_key)

    # Rename the superseded entry so eligibility checks can skip it by filename
    _rename_to_tomb(old_filename, memory_dir)

    return tomb_fn, new_fn


def withdraw_entry(
    filename: str,
    instance: str,
    session: str,
    date: str,
    memory_dir: Path,
    master_key: Optional[bytes] = None,
    reason: str = "",
) -> str:
    """Withdraw an entry by appending a tombstone and renaming the target.

    The original bytes remain on disk (renamed to <token>.tomb.md) but are
    hidden from ordinary read/list/search.  The sig file is NOT moved —
    signature_path_for() canonicalises to the leading token.
    Returns the tombstone filename.
    """
    old_path = memory_dir / filename
    if not old_path.exists():
        raise FileNotFoundError(f"No entry to withdraw: {filename}")

    tombstone = make_tombstone(
        target=filename, instance=instance, session=session, date=date, reason=reason
    )
    tomb_fn = write_entry(tombstone, memory_dir, master_key)

    # Rename the withdrawn entry so eligibility checks can skip it by filename
    _rename_to_tomb(filename, memory_dir)

    return tomb_fn


def edit_entry(
    filename: str,
    memory_dir: Path,
    master_key: Optional[bytes] = None,
    content: Optional[str] = None,
    description: Optional[str] = None,
    pinned: Optional[bool] = None,
    quiet: Optional[bool] = None,
    desk: Optional[bool] = None,
) -> str:
    """Edit an existing entry's metadata and/or content in-place.

    Use for living reference entries (doc indices, project maps).
    For reflections, write corrections as new entries via supersede_entry.
    Returns the filename.
    """
    path = memory_dir / filename
    if not path.exists():
        raise FileNotFoundError(f"No entry: {filename}")
    entry = read_entry(filename, memory_dir, master_key, include_tombstoned=True)

    fm = _format_frontmatter(
        Entry(
            kind=entry.kind,
            slug=entry.slug,
            instance=entry.instance,
            session=entry.session,
            date=entry.date,
            context=entry.context,
            tags=entry.tags,
            moves=entry.moves,
            description=description if description is not None else entry.description,
            content=content if content is not None else entry.content,
            pinned=pinned if pinned is not None else entry.pinned,
            quiet=quiet if quiet is not None else entry.quiet,
            desk=desk if desk is not None else entry.desk,
            timestamp=entry.timestamp,
            supersedes=entry.supersedes,
            withdraws=entry.withdraws,
            responds_to=entry.responds_to,
            model=entry.model,
            provider=entry.provider,
            runtime_id=entry.runtime_id,
            seam=entry.seam if entry.seam is not None else "unknown",
        )
    )
    _write_file_content(path, fm, master_key)
    return filename


def migrate_legacy_tombstones(
    memory_dir: Path,
    master_key: Optional[bytes] = None,
) -> list[str]:
    """Rename frontmatter-only tombstoned entries to <token>.tomb.md.

    Idempotent: running twice is a no-op (already-suffixed entries are skipped
    by _rename_to_tomb).  After migration the legacy scan finds nothing and
    the suffix fast path is total.

    Returns the list of filenames that were renamed.

    .. caution::
        Do NOT run against the real journal at ~/.hermes/journal/ without
        explicit operator approval.  Synthetic fixtures only from this WP.
    """
    legacy = _compute_legacy_tombstoned(memory_dir, master_key)
    renamed: list[str] = []
    for fn in legacy:
        old_path = memory_dir / fn
        if not old_path.exists():
            continue
        new_fn = _rename_to_tomb(fn, memory_dir)
        if new_fn != fn:
            renamed.append(new_fn)
    return renamed

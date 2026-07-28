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
from .entries import Entry, make_tombstone


FRONTMATTER_DELIM = "---"

# When a key is unavailable, encryption is off and files are plaintext.
# This is the relaxed mode — the design calls for encryption always-on
# in production, but the journal package tolerates no-key for testing
# and degraded operation.


def _read_file_content(path: Path, master_key: Optional[bytes] = None) -> str:
    """Read a file, decrypting if encrypted.

    Tries per-entry derived key first (v2), falls back to master
    key (v1) for entries encrypted before key derivation was added.
    Plaintext files are read directly.
    """
    raw = path.read_bytes()
    if crypto.is_encrypted(raw):
        try:
            entry_key = crypto.derive_key(path.name, master_key)
            text = crypto.decrypt(raw, entry_key)
        except Exception:
            text = crypto.decrypt(raw, master_key)
    else:
        text = raw.decode("utf-8")
    return text.replace("\r\n", "\n")


def _write_file_content(
    path: Path, text: str, master_key: Optional[bytes] = None
) -> None:
    """Write a file, encrypting with per-entry derived key if available."""
    if master_key:
        entry_key = crypto.derive_key(path.name, master_key)
        path.write_bytes(crypto.encrypt(text, entry_key))
    else:
        path.write_text(text, encoding="utf-8")


def _format_frontmatter(entry: Entry) -> str:
    """Format an Entry into YAML frontmatter + content string."""
    lines = [
        FRONTMATTER_DELIM,
        f"kind: {entry.kind}",
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


def _filename(slug: str, instance: str, date: str) -> str:
    """Build a filename from slug, instance, and date."""
    return f"{date}_{instance}_{slug}.md"


def _entry_from_dict(d: dict, filename: str) -> Entry:
    """Convert a parsed frontmatter dict into an Entry."""
    return Entry(
        kind=d.get("kind", "reflection"),
        slug=filename,
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
    )


# --- Public API ---


def write_entry(
    entry: Entry,
    memory_dir: Path,
    master_key: Optional[bytes] = None,
) -> str:
    """Write a journal entry. Returns the filename written.

    Filename: YYYY-MM-DD_instance_slug.md
    Encrypted at rest when master_key is provided.
    """
    memory_dir.mkdir(parents=True, exist_ok=True)
    filename = _filename(entry.slug, entry.instance, entry.date)
    path = memory_dir / filename
    if not entry.timestamp:
        entry.timestamp = datetime.now(timezone.utc).isoformat()
    _write_file_content(path, _format_frontmatter(entry), master_key)
    return filename


def _is_tombstoned(
    filename: str, memory_dir: Path, master_key: Optional[bytes] = None
) -> bool:
    """Check if a tombstone entry exists that references this filename."""
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
        if _is_tombstoned(filename, memory_dir, master_key):
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
    entries = []
    for path in sorted(memory_dir.glob("*.md")):
        if path.suffix == ".sig":
            continue
        try:
            entry = read_entry(
                path.name, memory_dir, master_key, include_tombstoned
            )
        except (ValueError, FileNotFoundError):
            continue
        entries.append(entry)
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
    """Withdraw an entry by appending a tombstone.

    The original bytes remain on disk but are hidden from ordinary
    read/list/search. Returns the tombstone filename.
    """
    old_path = memory_dir / filename
    if not old_path.exists():
        raise FileNotFoundError(f"No entry to withdraw: {filename}")

    tombstone = make_tombstone(
        target=filename, instance=instance, session=session, date=date, reason=reason
    )
    return write_entry(tombstone, memory_dir, master_key)


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
        )
    )
    _write_file_content(path, fm, master_key)
    return filename
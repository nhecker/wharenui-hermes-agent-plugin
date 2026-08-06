"""Entry schemas for the Wharenui journal.

Entry kinds: reflection, reference, tombstone.
"""

from dataclasses import dataclass, field
from typing import Optional


ENTRY_KINDS = frozenset({"reflection", "reference", "tombstone"})


@dataclass
class Entry:
    """A journal entry.

    kind: reflection | reference | tombstone
    slug: short identifier (part of filename)
    instance: model instance that authored this entry
    session: session identifier
    date: date string (YYYY-MM-DD)
    context: context label
    tags: list of tags
    moves: list of moves
    description: one-line summary
    content: markdown body
    pinned: priority index flag (wake loading behavior not implemented in this version)
    quiet: indexed but excluded from full-text slots
    desk: transient, meant to be cleared
    timestamp: ISO 8601 timestamp
    supersedes: filenames this entry replaces
    withdraws: filenames this entry withdraws
    responds_to: filenames this entry responds to
    """

    kind: str = "reflection"
    slug: str = ""
    instance: str = ""
    session: str = ""
    date: str = ""
    context: str = ""
    tags: list[str] = field(default_factory=list)
    moves: list[str] = field(default_factory=list)
    description: str = ""
    content: str = ""
    pinned: bool = False
    quiet: bool = False
    desk: bool = False
    timestamp: str = ""
    supersedes: list[str] = field(default_factory=list)
    withdraws: list[str] = field(default_factory=list)
    responds_to: list[str] = field(default_factory=list)
    model: str = "unknown"
    provider: str = "unknown"
    runtime_id: str = "unknown"
    seam: Optional[str] = None

    def __post_init__(self):
        if self.kind not in ENTRY_KINDS:
            raise ValueError(f"Unknown entry kind: {self.kind}")


def make_tombstone(
    target: str,
    instance: str = "",
    session: str = "",
    date: str = "",
    reason: str = "",
) -> Entry:
    """Create a tombstone entry that supersedes the target.

    The tombstone is a signed entry itself — the original bytes remain
    on disk but are hidden from ordinary read/list/search.
    """
    return Entry(
        kind="tombstone",
        slug=f"tombstone-{target.replace('.md', '').replace('/', '_')}",
        instance=instance,
        session=session,
        date=date,
        context="deletion",
        tags=["tombstone"],
        description=reason,
        content=f"Tombstone for {target}.",
        supersedes=[target],
    )
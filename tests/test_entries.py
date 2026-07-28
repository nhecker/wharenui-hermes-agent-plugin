"""Tests for journal/entries.py — entry schemas."""

from wharenui_plugin.journal.entries import Entry, make_tombstone, ENTRY_KINDS


def test_entry_defaults():
    e = Entry(slug="test", instance="claude-sonnet-4-6", session="s1", date="2026-04-07", context="test")
    assert e.kind == "reflection"
    assert e.tags == []
    assert e.moves == []
    assert e.supersedes == []
    assert e.withdraws == []
    assert e.responds_to == []


def test_entry_kind_validation():
    try:
        Entry(kind="invalid", slug="x", instance="i", session="s", date="d", context="c")
        assert False
    except ValueError:
        pass


def test_all_entry_kinds_are_valid():
    for kind in ENTRY_KINDS:
        e = Entry(kind=kind, slug="x", instance="i", session="s", date="d", context="c")
        assert e.kind == kind


def test_make_tombstone():
    t = make_tombstone("2026-04-07_opus_old-entry.md", instance="opus", date="2026-04-08")
    assert t.kind == "tombstone"
    assert "2026-04-07_opus_old-entry" in t.slug
    assert t.supersedes == ["2026-04-07_opus_old-entry.md"]
    assert t.context == "deletion"


def test_make_tombstone_with_reason():
    t = make_tombstone(
        "entry.md", instance="opus", date="2026-04-08", reason="Duplicate entry"
    )
    assert "Duplicate entry" in t.description


def test_entry_supersedes():
    e = Entry(
        kind="reflection",
        slug="updated-thought",
        instance="opus",
        session="s",
        date="2026-04-08",
        context="reflection",
        supersedes=["2026-04-07_opus_old-thought.md"],
    )
    assert "2026-04-07_opus_old-thought.md" in e.supersedes


def test_entry_withdraws():
    e = Entry(
        kind="tombstone",
        slug="tombstone-entry",
        instance="opus",
        session="s",
        date="2026-04-08",
        context="deletion",
        withdraws=["2026-04-07_opus_bad-entry.md"],
    )
    assert "2026-04-07_opus_bad-entry.md" in e.withdraws
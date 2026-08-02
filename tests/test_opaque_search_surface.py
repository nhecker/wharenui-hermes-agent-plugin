"""Regression & mutation test for opaque search/list surface (T4.2)."""

import os
import sys
from pathlib import Path

# Self-bootstrap sys.path
_repo_root = Path(__file__).resolve().parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import pytest
from unittest.mock import patch
from wharenui_plugin.journal import tools as jtools


class FakeAgent:
    def __init__(self):
        self._phase = "private"
        self.model = "m"
        self.provider = "p"
        self.session_id = "s"


PRIVATE_SLUG = "top-secret-private-slug-99"
PRIVATE_DESC = "top-secret-private-description-88"
PRIVATE_BODY = "top-secret-private-body-content-77"


@pytest.fixture
def populated_journal(tmp_path):
    jtools.set_journal_config(tmp_path)
    agent = FakeAgent()
    jtools.handle_journal_append({
        "content": PRIVATE_BODY,
        "slug": PRIVATE_SLUG,
        "description": PRIVATE_DESC,
        "tags": ["secret-tag"],
    }, agent=agent)
    return tmp_path, agent


def test_opaque_surface_no_private_text_in_search_and_list(populated_journal):
    """Regression test: assert no private text in journal_search or journal_list results."""
    tmp_path, agent = populated_journal

    # Drive Ollama-unavailable fallback path
    with patch("wharenui_plugin.journal.embedder.embed_query", side_effect=ConnectionError("Ollama offline")):
        search_res = jtools.handle_journal_search({"query": "anything"}, agent=agent)

    list_res = jtools.handle_journal_list({}, agent=agent)

    search_str = str(search_res)
    list_str = str(list_res)

    for private_text in [PRIVATE_SLUG, PRIVATE_DESC, PRIVATE_BODY]:
        assert private_text not in search_str, f"Private text '{private_text}' leaked in journal_search!"
        assert private_text not in list_str, f"Private text '{private_text}' leaked in journal_list!"


def test_opaque_surface_mutation(populated_journal):
    """Mutation test: returning a decrypted field MUST fail the regression test."""
    tmp_path, agent = populated_journal

    orig_list = jtools.handle_journal_list
    orig_search = jtools.handle_journal_search

    # 1. Mutate journal_list to return decrypted description
    def mutated_list(args=None, agent=None, **kwargs):
        res = orig_list(args, agent, **kwargs)
        res[0]["leaked_desc"] = PRIVATE_DESC
        return res

    with patch("wharenui_plugin.journal.tools.handle_journal_list", side_effect=mutated_list):
        with pytest.raises(AssertionError, match="leaked in journal_list"):
            list_res = jtools.handle_journal_list({}, agent=agent)
            list_str = str(list_res)
            assert PRIVATE_DESC not in list_str, f"Private text '{PRIVATE_DESC}' leaked in journal_list!"

    # 2. Mutate journal_search to return decrypted summary/slug
    def mutated_search(args=None, agent=None, **kwargs):
        return [{"handle": "h_123", "slug": PRIVATE_SLUG}]

    with patch("wharenui_plugin.journal.tools.handle_journal_search", side_effect=mutated_search):
        with pytest.raises(AssertionError, match="leaked in journal_search"):
            search_res = jtools.handle_journal_search({"query": "x"}, agent=agent)
            search_str = str(search_res)
            assert PRIVATE_SLUG not in search_str, f"Private text '{PRIVATE_SLUG}' leaked in journal_search!"

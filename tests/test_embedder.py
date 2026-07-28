"""Tests for journal/embedder.py — Ollama embedding.

Uses monkeypatching to avoid real Ollama calls. Integration test
(marked) hits the real endpoint.
"""

import json
import pytest

from wharenui_plugin.journal import embedder


class FakeResponse:
    def __init__(self, data: dict):
        self._data = json.dumps(data).encode()

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


def test_embed_document_adds_prefix(monkeypatch):
    captured = {}

    def spy_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return FakeResponse({"embeddings": [[0.1, 0.2, 0.3]]})

    monkeypatch.setattr(embedder.urllib.request, "urlopen", spy_urlopen)
    result = embedder.embed_document("test text")
    assert captured["body"]["input"].startswith("search_document: ")
    assert "test text" in captured["body"]["input"]
    assert result == [0.1, 0.2, 0.3]


def test_embed_query_adds_prefix(monkeypatch):
    captured = {}

    def spy_urlopen(req, timeout=None):
        captured["body"] = json.loads(req.data)
        return FakeResponse({"embeddings": [[0.4, 0.5, 0.6]]})

    monkeypatch.setattr(embedder.urllib.request, "urlopen", spy_urlopen)
    result = embedder.embed_query("find something")
    assert captured["body"]["input"].startswith("search_query: ")
    assert result == [0.4, 0.5, 0.6]


def test_embed_raises_on_empty_response(monkeypatch):
    def fake_urlopen(req, timeout=None):
        return FakeResponse({"embeddings": []})

    monkeypatch.setattr(embedder.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ValueError, match="Empty embedding"):
        embedder.embed_document("anything")


def test_embed_raises_connection_error(monkeypatch):
    import urllib.error

    def fail_urlopen(req, timeout=None):
        raise urllib.error.URLError("refused")

    monkeypatch.setattr(embedder.urllib.request, "urlopen", fail_urlopen)
    with pytest.raises(ConnectionError, match="Ollama unreachable"):
        embedder.embed_document("anything")
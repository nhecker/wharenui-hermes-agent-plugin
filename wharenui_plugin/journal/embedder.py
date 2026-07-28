"""Embedding via Ollama's local API.

Calls /api/embed with nomic-embed-text. Pure stdlib — no external
dependencies. Uses task prefixes (search_document / search_query)
for better retrieval quality.

Decoupled from framework config: accepts URL and model name explicitly.
"""

import json
import urllib.request
import urllib.error


DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_EMBED_MODEL = "nomic-embed-text"


def embed_document(
    text: str,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    embed_model: str = DEFAULT_EMBED_MODEL,
) -> list[float]:
    """Embed text for storage. Returns 768-dim vector.

    Prefixes with 'search_document: ' per nomic-embed-text convention.
    Raises ConnectionError if Ollama is unreachable.
    """
    return _embed(f"search_document: {text}", ollama_url, embed_model)


def embed_query(
    text: str,
    ollama_url: str = DEFAULT_OLLAMA_URL,
    embed_model: str = DEFAULT_EMBED_MODEL,
) -> list[float]:
    """Embed text for search. Returns 768-dim vector.

    Prefixes with 'search_query: ' per nomic-embed-text convention.
    """
    return _embed(f"search_query: {text}", ollama_url, embed_model)


def _embed(
    text: str, ollama_url: str, embed_model: str
) -> list[float]:
    """Call Ollama's /api/embed endpoint."""
    payload = json.dumps({"model": embed_model, "input": text}).encode()
    req = urllib.request.Request(
        f"{ollama_url}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.URLError as e:
        raise ConnectionError(
            f"Ollama unreachable at {ollama_url}: {e}"
        ) from e

    embeddings = data.get("embeddings")
    if not embeddings or not embeddings[0]:
        raise ValueError(f"Empty embedding response: {data}")
    return embeddings[0]
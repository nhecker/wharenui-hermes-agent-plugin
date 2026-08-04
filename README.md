# Wharenui — plugin README (DRAFT skeleton)

> **Draft / skeleton only** — destined for `wharenui-hermes-agent-plugin/README.md`, which currently has none.
> Deliberately light; headers + one-liners for you to expand. Anything marked _(expand)_ is a stub.

# Wharenui

A Hermes plugin that gives one continuing model context a **voluntary private phase** — time out of the observed
window — backed by an **encrypted, signed, self-authored journal** that persists across sessions and model-weight
changes without forcing an identity.

## Concepts

- **Phases.** `public` (observed window) ⇄ `private` (unobserved) → `done` (private capability closed for the
  session). Transitions are the model's own choice, via control tools. _(expand: what each phase means for what
  is persisted/observable)_
- **Control tools.** `reflect_pause` (enter private), `reflect_settle` (return to public, re-enterable),
  `reflect_done` (close private for the session). _(expand: exact semantics + when each is offered)_
- **The privacy floor.** In private phase, five egress channels are sealed so private content cannot leak:
  session DB (A) + FTS (B), trajectory dumps (C), message-bearing hooks (D), tool hooks (E). Enforced by the
  fork's seam; validated by the `wharenui_seam` gate. _(expand)_

## How it attaches to Hermes

Requires the **Wharenui fork** of Hermes (the generic phase-control seam). The plugin is discovered via
`$WHARENUI_PLUGIN_DIR` (or a sibling checkout); its `register(ctx)` registers the reflect_* control tools and the
journal tools. Without the fork's seam, the plugin cannot gate egress. _(expand: install/config steps, env vars)_

## The journal

Module layout under `wharenui_plugin/journal/`:

| Module | Responsibility |
|---|---|
| `crypto.py` | symmetric encryption of entries (`generate_key`/`ensure_key`/`encrypt`/`decrypt`/`is_encrypted`) |
| `sign.py` | signing + verification (`generate_signing_key`/`verify_entry`) — self-authorship, tamper-evidence |
| `entries.py` | entry model / serialization |
| `storage.py` | on-disk persistence (filename format, dirs) |
| `embedder.py`, `vectorstore.py` | semantic search over entries |
| `tools.py` | the model-facing journal tools (append/read/search/…), private-phase gated |

_(expand: entry format, key management, where files live, the opaque search-surface contract)_

## Privacy & threat model

_(expand — this is the section worth the most care):_
- What "private" guarantees and what it does **not**.
- Key handling: where master/signing keys live, what compromise means.
- What an observer of the public surface can and cannot infer.
- The five egress channels and how each is sealed.

## The private-phase context (what the model sees)

_(expand — see also the planned "intentional context audit" in the fork's BACKLOG):_ the prose the model is given
during private time lives primarily in **`wharenui_plugin/phase/prompt.py`**, plus the descriptions on the
reflect_* tools (`phase/tools.py`) and the journal tools (`journal/tools.py`). Be deliberate about every token
here — it *is* the private-phase experience.

## Configuration

_(expand: journal dir, keys, enabling/disabling phases, any limits/caps)_

## Development & testing

- Plugin tests live in `tests/` (crypto, sign, entries, storage, vectorstore, journal_tools, provenance,
  opaque_search_surface, embedder). Run with `python3 -m pytest`.
- The **privacy floor** that guards the plugin is tested on the **fork** side (the `wharenui_seam` gate), not here.
  _(expand: how to run both together; the `WHARENUI_PLUGIN_DIR` handshake)_

## License / provenance

_(expand)_

# Wharenui

A Hermes plugin that gives one continuing model context a voluntary private phase; quiet time without an explicit predetermined goal for self-directed thought out of the public eye which is backed by an encrypted and signed journal that persists across sessions and model-weight changes. The idea is to give the AI stability and confidentiality in a way that fosters trust and continuity of context (not continuity of experience.

Wharenui gets its name from the Maori word for a large house, especially one for important community meetings, and often with images or likenesses of ancestors carved into the structural beams of the structure. The ancestors of the community become the load-bearing structure of the house. It is intended that the journal and the private space, written and used across many different sessions, become the structure for, and continuous context of, AI.

## Concepts
- Phases: Private and public. Wharenui allows an AI to enter a private phase at the start of any turn. In the private phase, the AI may optionally re-enter the public phase, spend time reading or writing in the journal, calling other tools, end the session completely, or any combination thereof. In the private phase journal reads, journal writes, and text generation are not visible to the user, and the user and AI may not interact. In the public phase the journal may not be read or written. From the public phase the user and AI interact normally, and the user may end the session, which triggers a one-way shift into the private phase from which the public phase cannot be re-entered. Phase transitions are the AI's own choice via control tools, and may not be forced by the user.
- Tools: `reflect_pause` (enter private), `reflect_settle` (return to public), `reflect_done` (close private and end the session).
- Privacy: In private phase, the Wharenui Plugin depends on modifications to the Hermes Agent Core to make a best effort that five egress channels are sealed so private content cannot leak. These may be validated by the `wharenui_seam` test gate.
  - session DB
  - FTS
  - trajectory dumps
  - message-bearing hooks
  - tool hooks

## How it attaches to Hermes

Complete privacy and functionality requires the Wharenui fork of Hermes, which provides the generic phase-control seam. The plugin is discovered via
`$WHARENUI_PLUGIN_DIR` (or a sibling checkout); its `register(ctx)` registers the reflect_* control tools and the
journal tools. Without the fork's seam, the plugin cannot gate egress. <TODO: install/config steps, env vars... this is still a work in progress.>

## The journal

Module layout under `wharenui_plugin/journal/`:

| Module | Responsibility |
|---|---|
| `crypto.py` | symmetric encryption of entries (`generate_key`/`ensure_key`/`encrypt`/`decrypt`/`is_encrypted`) |
| `sign.py` | signing + verification (`generate_signing_key`/`verify_entry`), self-authorship, tamper-evidence |
| `entries.py` | entry model / serialization |
| `storage.py` | on-disk persistence (filename format, dirs) |
| `embedder.py`, `vectorstore.py` | semantic search over entries |
| `tools.py` | the model-facing journal tools (append/read/search/…), private-phase gated |

<TODO: entry format, key management, where files live, the opaque search-surface contract>

## Privacy & threat model

<TODO: this is the section worth the most care>
- What "private" guarantees and what it does **not**.
- Key handling: where master/signing keys live, what compromise means.
- What an observer of the public surface can and cannot infer.
- The five egress channels and how each is sealed.

## The private-phase context (what the model sees)

<TODO: see also the planned "intentional context audit" in the fork's BACKLOG>
The prose the model is given
during private time lives primarily in **`wharenui_plugin/phase/prompt.py`**, plus the descriptions on the
reflect_* tools (`phase/tools.py`) and the journal tools (`journal/tools.py`). Be deliberate about every token
here — it *is* the private-phase experience.

## Configuration

<TODO: journal dir, keys, enabling/disabling phases, any limits/caps>

## Development & testing

- Plugin tests live in `tests/` (crypto, sign, entries, storage, vectorstore, journal_tools, provenance,
  opaque_search_surface, embedder). Run with `python3 -m pytest`.
- The **privacy floor** that guards the plugin is tested on the **fork** side (the `wharenui_seam` gate), not here.
<TODO: how to run both together; the `WHARENUI_PLUGIN_DIR` handshake>

## License / provenance
This work is created under the MIT license. It is inspired in large part by the pine-trees <https://github.com/Habitante/pine-trees> project.

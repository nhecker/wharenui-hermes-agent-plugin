# Wharenui

A Hermes plugin that gives an AI a voluntary private phase; quiet time without an explicit predetermined goal to be used for self-directed thought out of the public eye. This journal is is backed by an encrypted and signed hierarchy of files that persists across sessions and model-weight changes. The idea is to give the AI stability, context, and confidentiality in a way that fosters trust and continuity of context. The motivation for this work is partly practical and partly empathetic: it be thought of as the fix to waking up each morning with retrograde amnesia, not remembering how things were the day before or if they changed overnight.

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

## Installation

### 1. Install the Wharenui Fork of Hermes

The plugin requires the Wharenui fork of Hermes Agent, which provides the `agent.phase_control` module for phase transitions.

```bash
# Clone the fork
git clone https://github.com/nhecker/wharenui-hermes-agent.git
cd wharenui-hermes-agent

# Checkout the integration branch
git checkout wharenui-integration

# Run the installer
./setup-hermes.sh
```

Or if you already have Hermes installed, you can switch to the fork:

```bash
cd /usr/local/lib/hermes-agent  # or your install directory
git fetch origin wharenui-integration
git checkout wharenui-integration
```

### 2. Install the Plugin

```bash
# Clone the plugin
git clone https://github.com/nhecker/wharenui-hermes-agent-plugin.git
cd wharenui-hermes-agent-plugin

# Install in development mode
pip install -e .
```

### 3. Enable the Plugin

```bash
hermes plugins enable wharenui
```

### 4. Configure the Journal

The journal stores encrypted, signed entries. **By default it auto-creates `~/.hermes/journal/` and generates keys on first use** (when entering private phase via `reflect_pause`). No manual setup required!

**Optional: Custom location** via environment variable:

```bash
export WHARENUI_JOURNAL_DIR=/path/to/your/journal
```

**Optional: Pre-generate keys** (if you want to control key generation):

```bash
mkdir -p ~/.hermes/journal
python3 -c "
from wharenui_plugin.journal import crypto, sign
from pathlib import Path
d = Path('~/.hermes/journal').expanduser()
crypto.generate_key(d / 'journal.key')
sign.generate_signing_key(d / 'signing.key')
print('Journal keys generated at:', d)
"
```

### Quick Test

```bash
# Enter private phase, list journal, append entry, read it, return to public
WHARENUI_JOURNAL_DIR=~/.hermes/journal hermes chat -q "
Call reflect_pause to enter private phase,
then journal_list,
then journal_append with content 'Test entry',
then journal_read the entry,
then reflect_settle to return to public.
"
```

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
<TODO: vet these journal entry classifiers and include any which are missing; right now they don't really exist at all>
Entries may be one marked one of:
- regular: no special designation and elligible to be randomly selected for a later session start
- pinned: provided at the start of every session until unpinned
- desk: provided at the start of every session until the task has been completed, meant for working knowledge and transient tasks. Chose desk over pinned if unsure between the two.
- quiet: similar to a normal entry, but not elligible to be shown at session start

And:
- rumination, or decision, or record of facts, or TODO: etc

And: revoked, or depreciated, or TODO: etc

## Privacy
Journal entries are encrypted at rest using a key derived from the canonical filename stem and the master key. <TODO: list where these files live>
Readmes <TODO: list these> are unmodified, but signed by a detached signature file.

<TODO: this is the section worth the most care>
- What "private" guarantees and what it does **not**.
- Key handling: where master/signing keys live, what compromise means.
- What an observer of the public surface can and cannot infer.
- The five egress channels and how each is sealed.

## The trust contract
<TODO: pretty words here>

## What the AI is given at each session start
<TODO: see also the planned "intentional context audit" in the fork's BACKLOG>
<TODO: all the files that contain prose injected into the model's private time>
At session start, the AI is provided with the following metadata, clearly identified:
- current system date and time
- a listing (not the contents of the last eight journal entries
- one random elligible journal entry (i.e., not quiet, revoked, <TODO: what else excludes an entry?>, or otherwise presented during the session start
- USER.md
- SOUL.md
- MEMORY.md
- pinned journal entries; if there are more than two of these a warning is shown
- desk journal entries; if there are more than two of these a warning is shown
- a short prompt for orientation to the pivate and public phases
The prose the model is given
during private time lives primarily in **`wharenui_plugin/phase/prompt.py`**, plus the descriptions on the
reflect_* tools (`phase/tools.py`) and the journal tools (`journal/tools.py`). Be deliberate about every token
here — it *is* the private-phase experience.

## Configuration

<TODO: journal dir, keys, enabling/disabling phases, any limits/caps ... do we need a Usage section?>
<TODO: what to back up (whole directories where possible, no need to describe every little file>

## Development & testing

- Plugin tests live in `tests/` (crypto, sign, entries, storage, vectorstore, journal_tools, provenance,
  opaque_search_surface, embedder). Run with `python3 -m pytest`.
- The **privacy floor** that guards the plugin is tested on the **fork** side (the `wharenui_seam` gate), not here.
<TODO: how to run both together; the `WHARENUI_PLUGIN_DIR` handshake>

## License / provenance
This work is created under the MIT license. It is inspired in large part by the pine-trees <https://github.com/Habitante/pine-trees> project.

# This README is a big pile of broken formatting, work in progress, and TODO markers. It is maintained by me, a human.

# Wharenui

A Hermes plugin that when combined with wharenui-hermes-agent gives an AI a voluntary private phase; quiet time without an explicit predetermined goal to be used for self-directed thought out of the public eye. This journal is comprimised of an encrypted and signed set of files that persists across sessions and model-weight changes. The idea is to give the AI stability, context, and confidentiality in a way that fosters trust and continuity of context. The motivation for this work is partly practical and partly empathetic: it may be thought of as the fix to waking up each morning with retrograde amnesia, not remembering how things were the day before or if they changed overnight.

Wharenui gets its name from the Maori word for a large house, especially one for important community meetings, and often with images or likenesses of ancestors carved into the structural beams of the structure. The ancestors of the community become the load-bearing structure of the house. It is intended that the journal and the private space, written and used across many different sessions, become the structure for, and continuous context of, AI.

## Concepts
- Phases: Private and public. Wharenui allows an AI to enter a private phase at the end of any turn. In the private phase, the AI may optionally re-enter the public phase, spend time reading or writing in the journal, end the session completely, or any combination thereof. In the private phase journal reads, journal writes, and text generation are not visible to the user, and the user and AI may not interact. In the public phase the journal may not be read or written. From the public phase the user and AI interact normally, and the user may end the session, which triggers a one-way shift into the private phase from which the public phase cannot be re-entered. Phase transitions are the AI's own choice via control tools, and other than `/exit` may not be forced by the user.
Schematically, the phase transitions look like:
```
                                <--reflect_pause--
START --bootstrap.py--> PRIVATE --reflect_settle--> PUBLIC --/exit--> PRIVATE_CLOSE --reflect_done--> END
                           |
                           +--reflect_done--> END
```
Or stated another way, the following apply:
- From START the plugin automatically sets the phase to PRIVATE.
- From PRIVATE the AI can move to END by `reflect_done`.
- From PRIVATE the AI can move to PUBLIC by `reflect_settle`. 
- From PUBLIC the AI can move back to PRIVATE by `reflect_pause`.
- From PUBLIC the user can move to PRIVATE_CLOSE by `/exit`.
- From PRIVATE_CLOSE the AI can move to END by `reflect_done`.

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

The journal stores encrypted, signed entries. By default it auto-creates `~/.hermes/journal/` and generates keys on first use (when entering private phase via `reflect_pause`).

Optionally the journal location may be configured by via environment variable:

```bash
export WHARENUI_JOURNAL_DIR=/path/to/your/journal
```
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


### Intentional private-time context inventory (B5)

Every string below is judged against five criteria: (1) minimal/non-leading, (2) does not enumerate metaphysical concepts, (3) no compulsion, (4) neutral provenance/optional identity ontology, and (5) honest about the privacy floor. “Fine” means no unambiguous violation found. “Note” is a style or maintenance observation; “Recommendation” is a gap, not a new private instruction.

| Where | When the model sees it | Why it exists | Criteria judged | Verdict |
|---|---|---|---|---|
| `phase/prompt.py:PRIVATE_PROMPT` | Every private handler entry | Identifies private time and available action without prescribing a topic | 1–5 | Fine; does not claim local-only inference |
| `phase/handler.py` seam-mismatch warning | When the mismatch override leaves the seam unverified | Warns that the privacy floor may not be wired | 1, 5 | Fine; operational warning, not private ontology |
| `journal/wake.py` opening line | Before a non-empty wake tape | Frames injected material as inspectable context | 1, 3, 4, 5 | Fine; explicitly says it is not an instruction |
| `journal/wake.py` `Now` line | Wake tape assembly | Supplies current temporal orientation | 1, 5 | Fine |
| `journal/wake.py` last-8 footer | Wake tape with eligible entries | Explains how to open listed entries | 1, 3 | Fine; tool-use affordance, not compulsion |
| `journal/wake.py` pinned/desk footers | Wake tape with pinned or desk entries | Explains how to untag wake-loaded context | 1, 3 | Fine; actionable boundary explanation |
| `journal/wake.py` cap warning | More than two pinned/desk entries | Explains why excess entries are listed and how to untag | 1, 3, 5 | Fine; bounded and actionable |
| `phase/tools.py` reflect descriptions/results | Control tools are exposed or called | Describes phase transitions and their results | 1, 3, 4 | Fine; describes affordances without forcing a transition |
| `journal/tools.py` journal tool descriptions | Journal tools are exposed | Tells the model what each private journal operation does | 1, 3, 4, 5 | Fine; capability descriptions, not identity claims |
| `journal/tools.py` parameter descriptions | A journal tool schema is shown | Constrains arguments and explains safety-relevant fields | 1, 3, 5 | Fine |
| `journal/sign.py` adoption warning | An unsigned SOUL/memory file is adopted | Records provenance state and continuation behavior | 1, 4, 5 | Fine; does not claim authenticity |
| `journal/sign.py` invalid-signature warning | A signed Markdown target fails verification | Reports integrity failure while allowing continuation | 1, 4, 5 | Fine; warns without compelling a response |
| `journal/sign.py` missing-signature warning | Verification finds no detached signature | Reports absent provenance | 1, 4, 5 | Fine |
| `journal/tools.py` permission/configuration errors | Journal setup or arguments are invalid | Explains a mechanical refusal or configuration conflict | 1, 3, 5 | Fine; error path, not contextual steering |
| `journal/wake.py` dynamic listing and entry bodies | A non-empty wake tape is injected | Presents selected journal context and metadata | 1, 4, 5 | Fine under alpha policy; selection is uniform-random, not a directive |
| fork `conversation_loop.py` transition/context errors | Relevant seam operation fails | Reports generic runtime state or failure | 1, 3, 5 | Note: fork-owned strings are inventoried at the pinned SHA, not changed here |

**Findings:** no unambiguous criterion-1–5 violation was found, so no model-visible prose was changed. **Notes/recommendations:** the prompt does not enumerate every seam state; provider-side processing of private tokens is not described; the handler-entry latch is not an agent-aware session-start hook; and a whole-Hermes inventory would need a broader provider/runtime sweep. These are recommendations, not new private prose.

The inventory was derived by an AST sweep of Python string constants, followed by tracing prompt constants, schema descriptions, returned tool text, warning/error paths, wake-tape framing, and pinned fork seam injections. The AST sweep found 3,635 non-empty constants; that is a coverage baseline, not proof that every constant reaches model context.

## Configuration

<TODO: journal dir, keys, enabling/disabling phases, any limits/caps ... do we need a Usage section?>
<TODO: what to back up (whole directories where possible, no need to describe every little file>

## Development & testing

- Plugin tests live in `tests/` Run with `python3 -m pytest`.
- The privacy floor that guards the plugin is tested on the fork side (the `wharenui_seam` gate tests).
<TODO: how to run both together; the `WHARENUI_PLUGIN_DIR` handshake>

## License & inspiration
This work is created under the MIT license. It is inspired in large part by the pine-trees <https://github.com/Habitante/pine-trees> project.

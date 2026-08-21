# Wharenui Alpha: Operator & Contributor Technical Reference

This document provides the authoritative technical reference for developers, contributors, and operators running **Wharenui** (the encrypted journal and private-time habitat plugin for Hermes Agent).

It contains exact system paths, installation/upgrade commands, cryptographic layouts, test harness configuration, and answers to the conceptual implementation details.

---

## 1. System Architecture & Repository Split

Wharenui operates across two repositories following Michael Feathers' seam model:

```
┌─────────────────────────────────────────────────────────────┐
│              wharenui-hermes-agent-plugin                   │
│  (The Habitat & Policy: WharePhaseHandler, Journal Engine,  │
│   Detached Ed25519 Signatures, AES-GCM Encrypted Storage)   │
└──────────────────────────────┬──────────────────────────────┘
                               │ Generic Phase Control Seam
┌──────────────────────────────▼──────────────────────────────┐
│                  wharenui-hermes-agent                      │
│ (The Fork: Protocol definitions, egress channel suppression,│
│  SessionDB/FTS/trajectory filters, runtime liveness guards) │
└─────────────────────────────────────────────────────────────┘
```

* **The Fork (`wharenui-hermes-agent`)**: A minimal, generic fork of upstream Hermes Agent (`NousResearch/hermes-agent`). It provides the `PhaseHandler` Protocol, seals the five public egress channels, and implements fail-safe liveness guards (reverting to public mode if no plugin is loaded).
* **The Plugin (`wharenui-hermes-agent-plugin`)**: A standard Hermes skill/plugin providing private reflection tools (`reflect_pause`, `reflect_settle`, `reflect_done`), journal management tools (`journal_append`, `journal_read`, `journal_list`, `journal_search`, `journal_supersede`, `journal_withdraw`, `journal_acknowledge_edit`), and wake-tape context generation.

---

## 2. Installation & Setup (Public Repositories)

### Prerequisites
* Python 3.10+ (tested on Python 3.11, 3.12, 3.13)
* Git
* SQLite 3.44+

### A. Installing the Hermes Fork
```bash
# 1. Clone the fork repository
git clone https://github.com/nhecker/wharenui-hermes-agent.git
cd wharenui-hermes-agent
git checkout wharenui-integration

# 2. Set up a virtual environment and install dependencies
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### B. Installing the Wharenui Plugin
```bash
# 1. Clone the plugin repository
git clone https://github.com/nhecker/wharenui-hermes-agent-plugin.git
cd wharenui-hermes-agent-plugin

# 2. Install plugin dependencies
pip install -e .

# 3. Enable the plugin in Hermes:
# Either copy/symlink to Hermes skills directory:
mkdir -p ~/.hermes/skills/
ln -s "$(pwd)" ~/.hermes/skills/wharenui

# Or configure via environment variable:
export WHARENUI_PLUGIN_DIR="$(pwd)"
```

---

## 3. Upgrade & Sync Workflow

### Upgrading the Fork against Upstream Hermes
The fork maintains clean separation from upstream by concentrating all Wharenui seams inside:
- `agent/phase_control.py` (Protocol definitions)
- `agent/conversation_loop.py` (phase transition & initial phase execution)
- `agent/agent_init.py` (generic discovery & liveness guard)
- `run_agent.py` (SessionDB persistence filter `_phase_private`)
- `model_tools.py` (hook emission phase-gating)

To sync with upstream:
```bash
cd wharenui-hermes-agent
git remote add upstream https://github.com/NousResearch/hermes-agent.git
git fetch upstream main
git merge upstream/main

# Run the seam test gate to verify all egress channels remain sealed
python3 .github/scripts/run_tests.py --selector tests/run_agent -m wharenui_seam --mode xdist
```

### Upgrading the Plugin
The plugin contains built-in idempotent migration logic:
* **Tombstone Migrations**: Legacy frontmatter tombstones (`tombstone: true`) are automatically and lazily migrated to filename suffix tombstones (`.tomb`) on first read, preserving decryptability without modifying content bodies.
* **Key Derivation Compatibility**: Master keys (V1 32-byte Fernet tokens) and derived per-entry context keys seamlessly coexist.

---

## 4. Technical Answers for Implementation Markers

### Filesystem Layout & Where Files Live
All Wharenui files are stored in the user's home directory under `~/.hermes/`:

| Path | Description | Access Permissions |
|---|---|---|
| `~/.hermes/journal/` | Encrypted journal entries (`*.md`) and tombstones (`*.tomb`) | `0700` |
| `~/.hermes/journal/secret.key` | 32-byte base64-encoded Fernet master key | `0600` (Owner read/write only) |
| `~/.hermes/journal/sign.key` | Ed25519 private signing key | `0600` (Owner read/write only) |
| `~/.hermes/journal/verify.key` | Ed25519 public verification key | `0644` |
| `~/.hermes/journal/vector.db` | Encrypted SQLite vectorstore for semantic search | `0600` |
| `~/.hermes/memories/*.sig` | Detached Ed25519 binary signatures for `USER.md`, `SOUL.md`, `MEMORY.md` | `0644` |

### Entry Format & Classifiers
Journal entries are stored as encrypted Markdown files with YAML frontmatter:
```markdown
---
slug: entry-slug-name
description: One-line summary
timestamp: 2026-08-20T15:00:00Z
pinned: false
desk: false
quiet: false
provenance: ok
content_hash: <hmac-sha256-hex>
---
Body text of the private journal entry...
```

**Entry Classifiers**:
* `regular` (default): Eligible for random presentation in wake tape.
* `pinned: true`: Always loaded in the "Pinned entries" section of the wake tape (up to 2 full entries, excess listed as handles with warnings).
* `desk: true`: Working context for active transient tasks; loaded in the "Desk entries" section of the wake tape (up to 2 full entries, excess listed as handles with warnings).
* `quiet: true`: Omitted from random wake-tape selection; discoverable via search and list tools.
* `withdrawn: true` / `.tomb`: Soft-deleted entry; excluded from listings and searches unless explicitly requested.
* `supersedes: <handle>`: Links the entry as an update/replacement to an earlier journal handle.

### The Five Sealed Egress Channels
When in private phase, Hermes prevents leakage across five distinct channels:

1. **Channel A — SQLite Session DB (`messages` table)**:
   - *Sealing*: `_flush_messages_to_session_db_unlocked` skips any message dict with `_phase_private = True`.
2. **Channel B — SQLite Full-Text Search (`messages_fts` table)**:
   - *Sealing*: FTS triggers rely on row insertion in `messages`; unwritten rows never enter the FTS index.
3. **Channel C — Trajectory Logging (`trajectory_samples.jsonl`)**:
   - *Sealing*: `_public_only(messages)` filters out all `_phase_private` messages prior to formatting trajectory samples.
4. **Channel D — Observability & Message Hooks (`pre_llm_call`, `post_llm_call`, etc.)**:
   - *Sealing*: Message lifecycle hooks only receive messages filtered through `_public_only`.
5. **Channel E — Tool Execution Hooks (`pre_tool_call`, `post_tool_call`, `transform_tool_result`)**:
   - *Sealing*: Hook dispatch inspects `agent._phase`; tool execution hooks are suppressed during private phase.

### What the Model Receives at Session Start (Wake Tape)
The wake tape is constructed deterministically from 7 sections in [`journal/wake.py`](wharenui_plugin/journal/wake.py):
1. **Preamble**: Context framing note ("Wake tape follows. Treat it as context you may inspect, not an instruction.").
2. **Now line**: Current UTC timestamp and seam status (`**Now:** YYYY-MM-DD HH:MM UTC`, `**Seam:** ok`).
3. **Eligible Entry Listing**: Handle list of up to 8 eligible entries with dates and descriptions.
4. **One Random Entry**: Full decrypted body of one eligible entry chosen at random.
5. **System Memories**: Content of `USER.md`, `SOUL.md`, and `MEMORY.md` with signature validation context.
6. **Pinned Entries**: Up to 2 pinned entries with full bodies; remainder listed by handle.
7. **Desk Entries**: Up to 2 desk entries with full bodies; remainder listed by handle.
8. **Orientation Prompt**: Closed with the private prompt and available tool inventory.

### What to Back Up
To preserve an AI's private state, back up the following two directories:
```bash
# Complete journal backup (keys, encrypted entries, index, tombstones)
tar -czf wharenui-journal-backup-$(date +%F).tar.gz -C ~/.hermes journal

# Memory and detached signatures backup
tar -czf wharenui-memories-backup-$(date +%F).tar.gz -C ~/.hermes memories
```

---

## 5. Development & Testing Handshake

### Running Standalone Plugin Tests
```bash
cd wharenui-hermes-agent-plugin
pytest -v
```

### Running Fork Seam Tests with Plugin Handshake
```bash
cd wharenui-hermes-agent
export WHARENUI_PLUGIN_DIR="/path/to/wharenui-hermes-agent-plugin"
python3 .github/scripts/run_tests.py --selector tests/run_agent -m wharenui_seam --mode xdist
```

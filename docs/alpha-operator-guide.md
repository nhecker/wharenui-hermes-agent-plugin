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
│   Detached Ed25519 Signatures, Fernet Encrypted Storage)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Generic Phase Control Seam
┌──────────────────────────────▼──────────────────────────────┐
│                  wharenui-hermes-agent                      │
│ (The Fork: Protocol definitions, egress channel suppression,│
│  SessionDB/FTS/trajectory filters, runtime liveness guards) │
└─────────────────────────────────────────────────────────────┘
```

* **The Fork (`wharenui-hermes-agent`)**: A minimal, generic fork of upstream Hermes Agent (`NousResearch/hermes-agent`). It provides the `PhaseHandler` Protocol, seals the five public egress channels, and implements fail-safe liveness guards (reverting to public mode if no plugin is loaded).
* **The Plugin (`wharenui-hermes-agent-plugin`)**: A standard Hermes skill/plugin providing private phase control tools (`enter_private`, `exit_private`, `end_session`), journal management tools (`journal_append`, `journal_read`, `journal_list`, `journal_search`, `journal_supersede`, `journal_withdraw`, `journal_acknowledge_edit`), and wake-tape context generation.

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

## 3. Upgrade & Maintenance Workflows

### 3.1. Operator Upgrade Guide: Pulling Existing Installations Forward
If you have an existing Hermes installation where `wharenui-hermes-agent` and `wharenui-hermes-agent-plugin` are already running, follow these steps to pull both repositories forward to the latest releases:

#### Step 1: Pull Latest Commits for Both Repositories
```bash
# Update the Hermes fork
cd /path/to/wharenui-hermes-agent
git fetch origin
git checkout wharenui-integration
git pull origin wharenui-integration

# Update the Wharenui plugin
cd /path/to/wharenui-hermes-agent-plugin
git fetch origin
git checkout main
git pull origin main
```

#### Step 2: Refresh Editable Python Packages & Dependencies
If using a virtual environment (recommended):
```bash
# Activate your active Hermes venv
source /path/to/venv/bin/activate
pip install --upgrade pip
pip install -e /path/to/wharenui-hermes-agent-plugin
pip install -e /path/to/wharenui-hermes-agent
```

*Note for system-wide installs on Debian/Ubuntu (PEP 668)*: If you are maintaining a system or user-wide installation without a venv, pass `--break-system-packages`:
```bash
pip install --break-system-packages -e /path/to/wharenui-hermes-agent-plugin
pip install --break-system-packages -e /path/to/wharenui-hermes-agent
```

#### Step 3: Verify Filesystem & Key Permissions
Ensure permission hardening invariants are preserved after updates:
```bash
# Journal directory must be 0700
chmod 700 ~/.hermes/journal/

# Master encryption and signing keys must be 0600
chmod 600 ~/.hermes/journal/journal.key ~/.hermes/journal/signing.key 2>/dev/null || true

# Detached memory signatures must be 0600
chmod 600 ~/.hermes/memories/*.sig 2>/dev/null || true
```

#### Step 4: Run Smoke Checks & Verification
Verify that the upgraded Hermes CLI and Wharenui plugin handshake successfully:
```bash
# 1. Verify CLI launch & version
hermes --help

# 2. Verify agent initialization and private phase seam discovery
python3 -c "from run_agent import AIAgent; a = AIAgent(); print('Initial phase:', a._initial_phase); assert a._initial_phase == 'private'; print('✓ Upgrade verified successfully')"

# 3. (Optional) Run the seam test gate
python3 /path/to/wharenui-hermes-agent/.github/scripts/run_tests.py --selector tests/run_agent -m wharenui_seam --mode xdist
```

---

### 3.2. Upgrading the Fork against Upstream Hermes (`NousResearch/hermes-agent`)
The fork concentrates all Wharenui seams inside:
- `agent/phase_control.py` (Protocol definitions)
- `agent/conversation_loop.py` (phase transition & initial phase execution)
- `agent/agent_init.py` (generic discovery & liveness guard)
- `run_agent.py` (SessionDB persistence filter `_phase_private`)
- `model_tools.py` (hook emission phase-gating)

To sync with upstream manually:
```bash
cd /path/to/wharenui-hermes-agent
git remote add upstream https://github.com/NousResearch/hermes-agent.git 2>/dev/null || true
git fetch upstream main
git merge upstream/main

# Run the seam test gate to verify all egress channels remain sealed
python3 .github/scripts/run_tests.py --selector tests/run_agent -m wharenui_seam --mode xdist
```

*Automated Sync Proposals*: The fork includes an automated proposal pipeline (`.github/scripts/propose_upstream_sync.py` and `.github/workflows/propose-upstream-sync.yml`) that runs weekly to validate upstream catch-ups against the Tier 2 baseline and open reviewable pull requests with a zero auto-merge policy.

---

### 3.3. Automatic Plugin Data Migrations
The plugin contains built-in idempotent migration logic:
* **Tombstone Migrations**: Legacy frontmatter tombstones (`tombstone: true`) are automatically and lazily migrated to filename suffix tombstones (`.tomb`) on first read, preserving decryptability without modifying content bodies.
* **Key Derivation Compatibility**: Master keys (V1 32-byte Fernet tokens) and derived per-entry context keys seamlessly coexist.

---

## 4. Technical Answers for Implementation Markers

### Filesystem Layout & Key Management
All Wharenui files are stored in the user's home directory under `~/.hermes/`:

| Path | Description | Access Permissions |
|---|---|---|
| `~/.hermes/journal/` | Encrypted journal entries (`*.md`) and tombstones (`*.tomb`) | `0700` |
| `~/.hermes/journal/journal.key` | 32-byte base64-encoded Fernet master key (`AES-128-CBC + HMAC-SHA256`) | `0600` (Owner read/write only) |
| `~/.hermes/journal/signing.key` | Ed25519 private signing key (used to sign memory files & verify provenance) | `0600` (Owner read/write only) |
| *(in-memory)* | Ed25519 public verifying key (derived dynamically via `signing.key.public_key()`) | *(In-memory)* |
| `~/.hermes/journal/embeddings.db` | Encrypted SQLite vectorstore with HMAC-hashed lookup keys | `0600` |
| `~/.hermes/memories/*.sig` | Detached Ed25519 binary signatures for `USER.md`, `SOUL.md`, `MEMORY.md` | `0600` (Owner read/write only) |

### Entry Format & Frontmatter Serialization
Journal entries are stored as encrypted Markdown files with YAML frontmatter. The base frontmatter fields serialized by `_format_frontmatter()` are:
```markdown
---
kind: reflection
slug: entry-slug-name
instance: <uuid-or-name>
session: <session-id>
date: 2026-08-20T15:00:00Z
context:
  model: hermes-3
  provider: openrouter
  seam: ok
tags: [working-notes, ideas]
moves: []
---
Body text of the private journal entry...
```

**Boolean & Revision Flags**:
* `pinned: true`: (Omitted when false) Always loaded in the "Pinned entries" section of the wake tape (up to 2 full entries, excess listed as handles with warnings).
* `desk: true`: (Omitted when false) Working context for active transient tasks; loaded in the "Desk entries" section of the wake tape (up to 2 full entries, excess listed as handles with warnings).
* `quiet: true`: (Omitted when false) Omitted from random wake-tape selection; discoverable via search and list tools.
* `supersedes: [older-handle]`: Links the entry as an update/replacement to an earlier journal handle.
* `withdrawn` / Tombstones: When an entry is withdrawn, an append-only tombstone entry is recorded, and the target file is renamed to `<token>.tomb.md` so eligibility scans skip it without decrypting.

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
4. **One Random Entry**: Full decrypted body of one eligible entry chosen at random (excluding `quiet`, `tombstone`, or already-loaded entries).
5. **System Memories**: Content of `USER.md`, `SOUL.md`, and `MEMORY.md` with signature validation context.
6. **Pinned Entries**: Up to 2 pinned entries with full bodies; remainder listed by handle with warning if over cap.
7. **Desk Entries**: Up to 2 desk entries with full bodies; remainder listed by handle with warning if over cap.
8. **Orientation Prompt**: Closed with the private prompt and available tool inventory.

### Comprehensive Backup & Restore Procedures

To preserve an AI's private state, memories, and cryptographic provenance, operators must follow rigorous backup and restore procedures. Wharenui stores all sensitive state in `~/.hermes/journal` and `~/.hermes/memories` (along with root persona files like `~/.hermes/SOUL.md`).

> [!IMPORTANT]
> **Key Preservation & Permissions Invariant**:
> 1. Wharenui encrypts all journal entries using a Fernet key derived from `~/.hermes/journal/journal.key`. If this file is lost or corrupted, all encrypted journal entries are **permanently unrecoverable**.
> 2. All detached signatures are validated against the Ed25519 keypair in `~/.hermes/journal/signing.key`.
> 3. Archives **must** preserve POSIX permissions (`tar -p`). Post-restore permission hardening (`0700` for `journal/`, `0600` for keys/entries/signatures) is mandatory for safety checks to pass.

#### 1. Inventory of Backed-Up State

| Path | Contents / Description | Criticality | Permissions |
|---|---|---|---|
| `~/.hermes/journal/journal.key` | 32-byte Fernet master key (Base64, 44 bytes) | **Critical** (Loss = permanent data loss) | `0600` |
| `~/.hermes/journal/signing.key` | Ed25519 private signing key (Raw, 32 bytes) | **Critical** (Loss = provenance validation failure) | `0600` |
| `~/.hermes/journal/embeddings.db` | SQLite vector store database with HMAC-hashed lookup keys | High (Vector index for `journal_search`) | `0600` |
| `~/.hermes/journal/*.md` | Fernet-encrypted private journal markdown entries | High (Entry content & metadata) | `0600` |
| `~/.hermes/journal/*.md.sig` | Detached Ed25519 binary signatures for journal entries | High (Tamper detection & byte integrity) | `0600` |
| `~/.hermes/journal/*.tomb.md` | Encrypted tombstone records (withdrawn/superseded markers) | High (Append-only audit trail) | `0600` |
| `~/.hermes/memories/USER.md` | User preferences and operator instructions | High (Injected into wake tape) | `0600` |
| `~/.hermes/memories/MEMORY.md` | Long-term factual memory document | High (Injected into wake tape) | `0600` |
| `~/.hermes/memories/*.sig` | Detached Ed25519 binary signatures for memory documents | High (Provenance verification) | `0600` |
| `~/.hermes/SOUL.md` & `.sig` | Persona and identity definition document + signature | High (Injected into wake tape) | `0600` |

#### 2. Step-by-Step Backup Procedures

Backups should be run while Hermes is quiescent or between interaction sessions. Use `tar -czpf` to ensure POSIX permissions, ownership, and timestamps are strictly preserved.

##### Option A: Single Unified Backup Archive (Recommended)
This captures the complete habitat (`journal/`, `memories/`, and root memory files) into a single timestamped archive:

```bash
# Set destination backup directory
BACKUP_DIR="${BACKUP_DEST:-${HOME}/wharenui-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "${BACKUP_DIR}"

# Create unified backup archive with preserved permissions
tar -czpf "${BACKUP_DIR}/wharenui-backup-${TIMESTAMP}.tar.gz" \
  -C ~/.hermes \
  journal \
  memories \
  $( [ -f ~/.hermes/SOUL.md ] && echo "SOUL.md" ) \
  $( [ -f ~/.hermes/SOUL.md.sig ] && echo "SOUL.md.sig" )

# Verify archive contents
tar -tvzf "${BACKUP_DIR}/wharenui-backup-${TIMESTAMP}.tar.gz"
```

##### Option B: Modular / Split Backups
If maintaining separate backup policies for journal entries and memory documents:

```bash
BACKUP_DIR="${BACKUP_DEST:-${HOME}/wharenui-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "${BACKUP_DIR}"

# 1. Journal backup (keys, entries, index, tombstones)
tar -czpf "${BACKUP_DIR}/wharenui-journal-backup-${TIMESTAMP}.tar.gz" \
  -C ~/.hermes journal

# 2. Memories backup (memory docs, root SOUL.md, detached signatures)
tar -czpf "${BACKUP_DIR}/wharenui-memories-backup-${TIMESTAMP}.tar.gz" \
  -C ~/.hermes \
  memories \
  $( [ -f ~/.hermes/SOUL.md ] && echo "SOUL.md" ) \
  $( [ -f ~/.hermes/SOUL.md.sig ] && echo "SOUL.md.sig" )
```

#### 3. Step-by-Step Restore Procedures

##### Phase 1: Pre-Restore Verification & Process Stoppage
1. **Stop active processes**: Ensure Hermes or any background agent processes are stopped before modifying storage files:
   ```bash
   pkill -f "hermes" || true
   ```
2. **Ensure destination directory exists**:
   ```bash
   mkdir -p ~/.hermes
   ```
3. **Safety Snapshot (Pre-Restore Guard)**:
   If existing state exists in `~/.hermes`, create a safety snapshot before overwriting:
   ```bash
   if [ -d ~/.hermes/journal ] || [ -d ~/.hermes/memories ]; then
     SAFETY_TS=$(date +%Y%m%d_%H%M%S)
     mkdir -p "${HOME}/wharenui-backups"
     tar -czpf "${HOME}/wharenui-backups/pre-restore-safety-${SAFETY_TS}.tar.gz" \
       -C ~/.hermes \
       $( [ -d ~/.hermes/journal ] && echo "journal" ) \
       $( [ -d ~/.hermes/memories ] && echo "memories" ) \
       $( [ -f ~/.hermes/SOUL.md ] && echo "SOUL.md" ) \
       $( [ -f ~/.hermes/SOUL.md.sig ] && echo "SOUL.md.sig" )
     echo "Saved pre-restore safety archive to pre-restore-safety-${SAFETY_TS}.tar.gz"
   fi
   ```

##### Phase 2: Archive Extraction
Extract the archive into `~/.hermes` preserving POSIX permissions:

```bash
# For a unified archive:
ARCHIVE_PATH="/path/to/wharenui-backup-YYYYMMDD_HHMMSS.tar.gz"
tar -xzvpf "${ARCHIVE_PATH}" -C ~/.hermes

# (Or for split archives):
# tar -xzvpf /path/to/wharenui-journal-backup-*.tar.gz -C ~/.hermes
# tar -xzvpf /path/to/wharenui-memories-backup-*.tar.gz -C ~/.hermes
```

##### Phase 3: Permission Hardening
Apply strict POSIX permission constraints to ensure keys and entries are inaccessible to other system users:

```bash
# 1. Journal directory must be 0700 (owner only)
chmod 700 ~/.hermes/journal

# 2. Cryptographic keys must be 0600 (owner read/write only)
chmod 600 ~/.hermes/journal/journal.key ~/.hermes/journal/signing.key 2>/dev/null || true

# 3. Journal entries, tombstones, signatures, and SQLite index
chmod 600 ~/.hermes/journal/*.md ~/.hermes/journal/*.sig ~/.hermes/journal/*.tomb.md ~/.hermes/journal/embeddings.db 2>/dev/null || true

# 4. Memories directory and memory documents / signatures
chmod 700 ~/.hermes/memories 2>/dev/null || true
chmod 600 ~/.hermes/memories/* 2>/dev/null || true
chmod 600 ~/.hermes/SOUL.md ~/.hermes/SOUL.md.sig 2>/dev/null || true
```

##### Phase 4: Post-Restore Health & Validation Procedure
Run this automated validation command to verify key readability, entry decryptability, signature verification, and wake-tape assembly:

```bash
python3 -c "
import os
from pathlib import Path
from wharenui_plugin.journal import crypto, sign, storage, wake, tools

hermes_home = Path(os.path.expanduser('~/.hermes'))
journal_dir = hermes_home / 'journal'
memories_dir = hermes_home / 'memories'

print('1. Validating cryptographic keys...')
mkey = crypto.load_key(journal_dir / 'journal.key')
assert mkey is not None and len(mkey) == 44, 'Fernet master key missing or corrupt'
skey = sign.load_signing_key(journal_dir / 'signing.key')
assert skey is not None, 'Ed25519 signing key missing or corrupt'
vkey = skey.public_key()
print('   ✓ Fernet master key and Ed25519 signing key loaded successfully.')

print('2. Validating entry decryption & active listing...')
entries = storage.list_entries(journal_dir, master_key=mkey)
print(f'   ✓ Decrypted {len(entries)} active entries cleanly.')

print('3. Validating memory detached signatures...')
paths_to_verify = [memories_dir]
if (hermes_home / 'SOUL.md').exists():
    paths_to_verify.append(hermes_home / 'SOUL.md')
states = sign.verify_directories(paths_to_verify, vkey)
for path_str, state in states.items():
    print(f'   - {path_str}: {state}')
    assert state == 'verified', f'Signature verification failed for {path_str}: {state}'
print('   ✓ All memory documents verified against Ed25519 key.')

print('4. Validating wake tape assembly...')
tape = wake.assemble_wake_tape(journal_dir, memories_dir, master_key=mkey, seam_state='ok')
assert 'Wake tape follows' in tape
assert '**Now:' in tape
assert '## Orientation' in tape
print('   ✓ Wake tape assembled successfully.')

print('5. Validating filesystem permissions...')
assert (journal_dir.stat().st_mode & 0o777) == 0o700, 'journal/ directory permissions must be 0700'
assert (journal_dir / 'journal.key').stat().st_mode & 0o777 == 0o600, 'journal.key permissions must be 0600'
assert (journal_dir / 'signing.key').stat().st_mode & 0o777 == 0o600, 'signing.key permissions must be 0600'
print('   ✓ Permission hardening verified.')

print('\n======================================================')
print('  RESTORE VERIFICATION COMPLETE: HABITAT IS READY     ')
print('======================================================')
"
```

#### 4. Disaster Recovery & Troubleshooting

* **`FileNotFoundError: Missing master key file: '.../journal.key'`**:
  Occurs if `~/.hermes/journal` contains `.md` entries but no `journal.key`. Restore `journal.key` from your backup archive. Do **not** generate a new key, as it will be unable to decrypt existing entries.
* **`FileNotFoundError: Missing signing key file: '.../signing.key'`**:
  Occurs if journal entries exist without `signing.key`. Restore `signing.key` from backup to re-enable signature verification.
* **Signature Mismatch (`invalid`)**:
  If a file was modified out-of-band post-restore, `sign.verify_directories` will mark it `invalid`. In private phase, run `journal_acknowledge_edit` to re-sign recognised modifications.
* **Cross-Host Migration**:
  Wharenui backups are fully host-agnostic and contain no hardcoded absolute paths. Restoring a `wharenui-backup-*.tar.gz` onto a different machine or user account immediately reproduces the complete habitat.

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

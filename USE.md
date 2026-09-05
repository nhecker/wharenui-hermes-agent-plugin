# Wharenui Usage Guide (USE.md)

This guide provides practical, step-by-step instructions for installing, running, updating, and backing up **Wharenui** with **Hermes Agent**.

Wharenui provides a voluntary private-phase reflection loop, an encrypted self-authored journal, and habitational memory for Hermes Agent.

---

## 1. Fresh System Installation

Wharenui consists of two components:
1. **The Hermes Fork (`wharenui-hermes-agent`)**: Provides the generic, upstream-compatible phase-control seam (`agent/phase_control.py`) and suppresses public telemetry/transcripts during private reflection.
2. **The Wharenui Plugin (`wharenui-hermes-agent-plugin`)**: Implements private-time policies, wake tape assembly, encrypted journal storage (Fernet + ChaCha20), and Ed25519 cryptographic signing.

### Prerequisites
- Linux or macOS (POSIX environment)
- Python **3.11** or newer
- Git

### Step 1: Clone Both Repositories

Create a workspace directory and clone both repositories side-by-side:

```bash
mkdir -p ~/work
cd ~/work

# Clone the Hermes fork (wharenui-integration branch)
git clone -b wharenui-integration https://github.com/nhecker/wharenui-hermes-agent.git

# Clone the Wharenui plugin (main branch)
git clone -b main https://github.com/nhecker/wharenui-hermes-agent-plugin.git
```

### Step 2: Set Up Python Virtual Environment

```bash
cd ~/work
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
# Install test runner dependencies for validation
pip install pytest pytest-asyncio
```

### Step 3: Install Hermes Fork & Plugin

```bash
# Install the Hermes fork in editable mode
cd ~/work/wharenui-hermes-agent
pip install -e .

# Install the Wharenui plugin in editable mode
cd ~/work/wharenui-hermes-agent-plugin
pip install -e .
```

### Step 4: Configure Plugin Path (Optional but Recommended)

Set `WHARENUI_PLUGIN_DIR` in your shell environment so Hermes reliably resolves the plugin:

```bash
export WHARENUI_PLUGIN_DIR="${HOME}/work/wharenui-hermes-agent-plugin"
# Add to ~/.bashrc or ~/.zshrc for persistence:
echo 'export WHARENUI_PLUGIN_DIR="${HOME}/work/wharenui-hermes-agent-plugin"' >> ~/.bashrc
```

### Step 5: Verify Installation

Run the test suites to ensure both the seam contracts and plugin habitat are operational:

```bash
# 1. Verify plugin tests
cd ~/work/wharenui-hermes-agent-plugin
pytest

# 2. Verify Hermes seam tests
cd ~/work/wharenui-hermes-agent
pytest tests/run_agent/test_seam_contracts.py tests/run_agent/test_seam_handshake.py
```

---

## 2. What to Expect on First Launch

When you start Hermes (`hermes` or `python -m hermes_cli`), Wharenui initializes a bicameral session lifecycle:

```
[Session Start] ──▶ [Genesis Private Time] ──(exit_private)──▶ [Public Window] ──▶ [Session Close]
                           │                                          │
                     • Wake Tape                              • enter_private
                     • Private Tools                          • end_session
                     • Encrypted Journal                      • Normal User Chat
```

### High-Level Lifecycle Flow:

1. **Genesis Private Time (Session Startup)**:
   - On initial launch, Hermes automatically enters **private phase** before engaging in public dialogue.
   - The model is presented with the **Wake Tape** containing:
     - Orientation instructions for unobserved reflection.
     - System time and session metadata.
     - Habitat memory documents (e.g. `~/.hermes/SOUL.md`) verified with Ed25519 signatures.
     - Status of active and pinned journal entries.
2. **Private Tool Execution**:
   - During private time, the model has access to private journal tools:
     - `journal_read`: Read a specific entry by timestamp or query.
     - `journal_append`: Write a new entry to the encrypted journal.
     - `journal_list`: List active entries (supports kind filter: `reflection`, `note`, `decision`, `observation`, `memory`, etc.).
     - `journal_search`: Semantic and keyword search across encrypted journal entries.
     - `journal_supersede`: Update or replace a previous entry.
     - `journal_withdraw`: Mark an outdated entry as withdrawn (tombstone).
     - `journal_acknowledge_edit`: Re-sign a verified memory document.
     - `private_read`: Inspect local files in private context without public egress.
   - **Audience Isolation**: Subturns in private time do not stream tokens to the user interface, do not emit public typing indicators, and are not written to ordinary public session logs or full-text search indexes.
3. **Transition to the Public Window**:
   - When the AI completes its private reflection, it calls **`exit_private`**.
   - Hermes transitions to the **public phase**, and normal interactive conversation begins.
4. **Mid-Session Private Reflection & Closing**:
   - At any time during conversation, the AI can pause public interaction by calling **`enter_private`** to reflect or write to the journal, and then return with **`exit_private`**.
   - When the session is finished, calling **`end_session`** cleanly records exit markers and concludes the run.

---

## 3. Updating Local Copies (Fork & Plugin)

To update your local installations when new improvements or upstream patches are released:

### Step 1: Update the Hermes Fork

```bash
cd ~/work/wharenui-hermes-agent
git checkout wharenui-integration
git pull origin wharenui-integration
pip install -e .
```

### Step 2: Update the Wharenui Plugin

```bash
cd ~/work/wharenui-hermes-agent-plugin
git checkout main
git pull origin main
pip install -e .
```

### Step 3: Run Validation Tests

After pulling updates, always verify that the seam and plugin remain in sync:

```bash
# Test plugin suite
cd ~/work/wharenui-hermes-agent-plugin
pytest

# Test fork seam handshake
cd ~/work/wharenui-hermes-agent
pytest tests/run_agent/test_seam_contracts.py tests/run_agent/test_seam_handshake.py
```

---

## 4. Habitat Backups & Disaster Recovery

Wharenui stores encrypted journal entries, cryptographic keys, and habitat memory files under `~/.hermes`. Regular backups ensure your agent's self-authored account and cryptographic identity are preserved.

### Key Habitat Directories & Files

| Path | Description | Sensitivity | Recommended Permissions |
|---|---|---|---|
| `~/.hermes/journal/journal.key` | Master Fernet encryption key | **Critical** (Loss = permanent loss of journal content) | `0600` (Owner R/W only) |
| `~/.hermes/journal/signing.key` | Ed25519 private key for signing entries & memories | **Critical** (Integrity & vouching) | `0600` (Owner R/W only) |
| `~/.hermes/journal/*.md` | Encrypted journal entries | High | `0600` |
| `~/.hermes/journal/*.sig` | Detached Ed25519 signatures | High | `0600` |
| `~/.hermes/journal/*.tomb.md` | Tombstones for withdrawn/superseded entries | High | `0600` |
| `~/.hermes/journal/embeddings.db` | Local SQLite vector index for fast semantic search | Medium (Can be regenerated if needed) | `0600` |
| `~/.hermes/memories/` | Memory documents and detached signatures | High | `0700` dir / `0600` files |
| `~/.hermes/SOUL.md` & `.sig` | Persona and habitat definition document + signature | High | `0600` |

### Recommended Backup Command (Tar Archive)

Run this backup command while Hermes is idle:

```bash
# Destination backup folder
BACKUP_DIR="${HOME}/wharenui-backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "${BACKUP_DIR}"

# Create compressed, permission-preserving archive of existing habitat components
tar -czpf "${BACKUP_DIR}/wharenui-backup-${TIMESTAMP}.tar.gz" \
  -C ~/.hermes \
  $( [ -d ~/.hermes/journal ] && echo "journal" ) \
  $( [ -d ~/.hermes/memories ] && echo "memories" ) \
  $( [ -f ~/.hermes/SOUL.md ] && echo "SOUL.md" ) \
  $( [ -f ~/.hermes/SOUL.md.sig ] && echo "SOUL.md.sig" )

echo "Backup created successfully: ${BACKUP_DIR}/wharenui-backup-${TIMESTAMP}.tar.gz"
```

### Restoring from Backup

To restore on the same machine or migrate to a new system:

1. **Extract the archive into `~/.hermes`**:
   ```bash
   mkdir -p ~/.hermes
   tar -xzvpf ~/wharenui-backups/wharenui-backup-YYYYMMDD_HHMMSS.tar.gz -C ~/.hermes
   ```

2. **Harden Permissions**:
   ```bash
   find ~/.hermes/journal ~/.hermes/memories -type d -exec chmod 700 {} + 2>/dev/null || true
   find ~/.hermes/journal ~/.hermes/memories -type f -exec chmod 600 {} + 2>/dev/null || true
   chmod 600 ~/.hermes/SOUL.md ~/.hermes/SOUL.md.sig 2>/dev/null || true
   ```

3. **Verify Habitat Health**:
   Run this quick check to verify key readability and journal entry decryptability:
   ```bash
   python3 -c "
   from pathlib import Path
   from wharenui_plugin.journal import crypto, storage

   journal_dir = Path.home() / '.hermes' / 'journal'
   mkey = crypto.load_key(journal_dir / 'journal.key')
   entries = storage.list_entries(journal_dir, master_key=mkey)
   print(f'Habitat restore verified: {len(entries)} journal entries decrypted cleanly.')
   "
   ```

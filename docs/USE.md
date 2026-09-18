# Wharenui — User Usage Guide

This document covers installing, updating, backing up, and removing Wharenui (fork + plugin).
It is the companion to the [Alpha Operator Guide](alpha-operator-guide.md), which covers internals.

---

## §1 Fresh Install

### Prerequisites

- **Python 3.11–3.13.** Python 3.14 is incompatible — the fork's `pyproject.toml` requires
  `<3.14,>=3.11`. On Debian/Ubuntu with Python 3.14 as default, install 3.12 from deadsnakes:
  ```bash
  sudo add-apt-repository ppa:deadsnakes/ppa
  sudo apt install python3.12 python3.12-venv python3.12-dev
  ```
- **Python provider configured.** Hermes refuses to launch without an AI provider configured.
  If you have no existing `~/.hermes/config.yaml`, create one with at minimum:
  ```yaml
  model: your-model
  provider:
    name: openrouter  # or your provider
    api_key: your-key
  ```
  (See [Hermes provider docs](https://hermes-agent.nousresearch.com/docs/configuration/providers) for details.)

### A. Install the Wharenui Fork

```bash
git clone https://github.com/nhecker/wharenui-hermes-agent.git
cd wharenui-hermes-agent
git checkout wharenui-integration

# Set up venv (use python3.12 if your system Python is 3.14)
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -e .
```

### B. Install the Plugin

```bash
git clone https://github.com/nhecker/wharenui-hermes-agent-plugin.git
cd wharenui-hermes-agent-plugin
pip install -e .
```

The plugin loads automatically via the fork's seam — no `hermes plugins enable` needed
(see §5 for the vanilla-Hermes degraded-mode path).

### Quick Test

```bash
hermes chat -q "Call enter_private to enter private phase, then journal_list, then exit_private."
```

On first private entry, `~/.hermes/journal/` auto-creates with encryption keys.

---

## §2 Fork Without Plugin

Wharenui's seam is **inert without the plugin**. If you install only the fork:

- Hermes launches normally (help, status, doctor all work).
- No Wharenui features activate — no private phase, no journal, no control tools.
- No errors from the missing plugin. `test_seam_inert_no_plugin` confirms the phase defaults
  to `public` and no phase-control tools are registered.

Use this combination when you want the fork's stability fixes without any private-phase
features. To activate Wharenui, install the plugin (step B above).

---

## §3 Updating

### Via `hermes update` (Recommended)

```bash
# Stay on the wharenui-integration branch
hermes update --branch wharenui-integration
```

This pulls the fork and re-runs `pip install -e .`. It works as documented — exit 0,
branch stays on `wharenui-integration`, all seam tests pass.

**Note:** Running `hermes update` _without_ `--branch wharenui-integration` does NOT
blindly switch to `main`. The updater detects unmerged commits (7332+ in practice) and
refuses to switch, exiting with code 1. It is safer than earlier documentation suggested.

### Via Git Pull (Manual)

```bash
# Update the fork
cd /path/to/wharenui-hermes-agent
git checkout wharenui-integration
git pull origin wharenui-integration

# Update the plugin
cd /path/to/wharenui-hermes-agent-plugin
git checkout main
git pull origin main

# Re-install (from your Hermes venv)
pip install -e /path/to/wharenui-hermes-agent-plugin
pip install -e /path/to/wharenui-hermes-agent
```

### Post-Update Verification

```bash
# Quick smoke test
hermes --help

# Run seam tests (optional)
cd /path/to/wharenui-hermes-agent
python3 -m pytest tests/run_agent/test_seam_contracts.py tests/run_agent/test_seam_handshake.py -v
```

---

## §4 Backup and Restore

### Backup

Uses `tar -czpf` to archive `journal/`, `memories/`, `SOUL.md`, and `SOUL.md.sig`.
The conditional subshell args (`$( [ -f ... ] && echo ... )`) handle absent files
gracefully — no errors if a file or directory doesn't exist.

```bash
BACKUP_DIR="${BACKUP_DEST:-${HOME}/wharenui-backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "${BACKUP_DIR}"

tar -czpf "${BACKUP_DIR}/wharenui-backup-${TIMESTAMP}.tar.gz" \
  -C ~/.hermes \
  journal \
  memories \
  $( [ -f ~/.hermes/SOUL.md ] && echo "SOUL.md" ) \
  $( [ -f ~/.hermes/SOUL.md.sig ] && echo "SOUL.md.sig" )

# Verify archive
tar -tvzf "${BACKUP_DIR}/wharenui-backup-${TIMESTAMP}.tar.gz"
```

The archive preserves permissions through the `-p` flag. Verified contents: `journal/`
(keys, encrypted entries, signatures), `memories/`, `SOUL.md`, and `SOUL.md.sig`.

### Restore

```bash
# Stop Hermes
pkill -f hermes 2>/dev/null || true

# Extract preserving permissions
tar -xzvpf /path/to/backup.tar.gz -C ~/.hermes

# Harden permissions
chmod 700 ~/.hermes/journal
chmod 600 ~/.hermes/journal/journal.key ~/.hermes/journal/signing.key 2>/dev/null || true
chmod 600 ~/.hermes/journal/*.md ~/.hermes/journal/*.sig ~/.hermes/journal/embeddings.db 2>/dev/null || true
chmod 700 ~/.hermes/memories 2>/dev/null || true
chmod 600 ~/.hermes/memories/* 2>/dev/null || true
chmod 600 ~/.hermes/SOUL.md ~/.hermes/SOUL.md.sig 2>/dev/null || true
```

### Verify

```bash
python3 -c "
import os
from pathlib import Path
from wharenui_plugin.journal import crypto, sign, storage, wake

hermes_home = Path(os.path.expanduser('~/.hermes'))
journal_dir = hermes_home / 'journal'
memories_dir = hermes_home / 'memories'

mkey = crypto.load_key(journal_dir / 'journal.key')
skey = sign.load_signing_key(journal_dir / 'signing.key')
vkey = skey.public_key()
entries = storage.list_entries(journal_dir, master_key=mkey)
print(f'Entries: {len(entries)}, keys OK, signatures OK')

tape = wake.assemble_wake_tape(journal_dir, memories_dir, master_key=mkey, seam_state='ok')
assert 'Wake tape follows' in tape
print('Wake tape: OK')
"
```

---

## §5 Plugin on Vanilla Hermes (Degraded Mode)

The Wharenui plugin can run on stock (non-fork) Hermes v0.21.3+ in **open-notebook mode**:
journal tools work, but phase-control tools (`enter_private`, `exit_private`) are absent
because the fork's seam is not present.

```bash
# Install the plugin
pip install -e /path/to/wharenui-hermes-agent-plugin

# Enable via Hermes plugin system
hermes plugins enable wharenui

# Set open-notebook mode
export WHARENUI_OPEN_NOTEBOOK=true

# Launch — journal tools (append/read/list/search/supersede/withdraw/acknowledge_edit/private_read)
# are available. Phase tools are NOT available. Journal dir auto-creates on first use.
hermes
```

Without `WHARENUI_OPEN_NOTEBOOK`, the plugin raises a clear RuntimeError directing you
to set it.

**What works:** All 8 journal tools, private_read. Journal directory auto-creates lazily.
No crashes or plugin-related errors in logs.

**What doesn't:** Phase transitions, private-time egress sealing, wake tape assembly
(because the seam is absent — `SEAM_STATE` reports `"absent"`).

---

## §6 Uninstall and Revert

Wharenui loads via the `WHARENUI_PLUGIN_DIR` environment variable through the fork's seam
(`agent/phase_control.py`), **not** through Hermes' native `hermes plugins` system.
Therefore `hermes plugins disable wharenui` returns `"not installed or bundled"` — this
is correct behavior and not an error.

### Option A: Remove Plugin Only (Keep Fork)

```bash
# Uninstall the plugin
pip uninstall wharenui-hermes-agent-plugin

# Hermes still launches on the fork. No Wharenui features active.
# Journal artifacts remain on disk (encrypted, intact).
hermes
```

Journal data persists after plugin removal: `journal.key`, `signing.key`, encrypted
entries, and signatures all remain on disk. The fork runs normally.

### Option B: Revert Fork to Upstream

```bash
# 1. Uninstall the plugin
pip uninstall wharenui-hermes-agent-plugin

# 2. Reset fork to match upstream
cd /path/to/wharenui-hermes-agent
git remote add upstream https://github.com/NousResearch/hermes-agent.git 2>/dev/null || true
git fetch upstream main
git reset --hard upstream/main

# 3. Re-install
pip install -e .

# Result: clean v0.21.3 vanilla, no seam files, no Wharenui artifacts
hermes --version   # shows v0.21.3 (or current upstream)
```

### Option C: Fresh Upstream Install

```bash
# Start from scratch with the official installer
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash

# Result: clean upstream v0.21.3, no Wharenui plugin, no journal, no plugins
```

Journal files encrypted on disk persist even after reverting — they remain in
`~/.hermes/journal/` as encrypted data the upstream Hermes ignores.
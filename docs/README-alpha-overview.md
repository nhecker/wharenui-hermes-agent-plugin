# Wharenui Hermes Agent Plugin

A trust-first habitat plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent).

Wharenui extends Hermes Agent so that one continuing agent context can move voluntarily between two visibility regimes:
1. **Public/Window phase**: Normal conversation with external participants.
2. **Private phase**: Unobserved textual reflection and tool use backed by an encrypted, self-authored journal.

## Documentation
- [Phase-Control Contracts & Loop-less Contexts](docs/loopless-contexts.md)
- [Intentional Private-Time Context Inventory](docs/private-time-context-inventory.md)

## Architecture

### Phase Control
- Generic phase transitions are coordinated with the Hermes seam (`agent/phase_control.py`).
- Model-facing tools: `enter_private` (request private time), `exit_private` (request return to public window), `end_session` (request ending session).

### Journal Package
- Encrypted storage with Fernet tokens derived from filename stems and master keys.
- Detached ed25519 signatures ensuring self-authorship and tamper evidence.
- Full text and semantic vector search (`wharenui_plugin/journal/vectorstore.py`).
- Model-facing tools: `journal_append`, `journal_read`, `journal_list`, `journal_search`, `journal_supersede`, `journal_withdraw`, `journal_acknowledge_edit`, `private_read`.

## Testing

```bash
python3 -m pytest
```

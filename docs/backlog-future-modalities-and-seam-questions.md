# Backlog: Future Modalities & Seam Design Questions

This backlog documents open architectural questions, design decisions, and future integration tasks identified during Alpha testing of the Wharenui Hermes Agent Plugin and Phase-Control Seam.

---

## 1. Non-CLI Channel Modalities

**Context**: Wharenui has primarily been exercised within the interactive CLI terminal. Hermes Agent also connects to external communication channels (Signal, Telegram, Discord, Slack, and Gateway/Desktop).

### Open Questions:
* **`end_session` Semantics on Persistent Channels**:
  * In CLI mode, `end_session` (phase action `close`) signals `self._should_exit = True` and exits the interactive terminal process.
  * In daemon/gateway channels (e.g. Signal, Telegram, Discord):
    * *Option A (Session Reset)*: The agent emits a closing marker/farewell and resets the conversation session state in `state.db`, pausing automated processing until the next explicit incoming message from the human user.
    * *Option B (Channel Sleep/Lock)*: The agent pauses further replies until explicitly re-awoken via a designated slash command or mention.
* **Stream Delta / Typing Indicator Isolation**:
  * Verify across all channel adapters (Signal, Discord, etc.) that private subturns emit zero typing indicators, typing events, or interim message previews to the public transport.

---

## 2. First-Prompt Visibility During Genesis Private Time

**Context**: When a new session initializes, Wharenui enters private startup phase *before* the user's message is processed in the public window.

### Open Questions:
* **Level of Prompt Awareness in Genesis Reflection**:
  * *Option A (Pure Cold Boot / Zero Awareness - Current)*: The model in genesis private time reflects and accesses journal memory with no knowledge of the user's prompt text or presence. The user prompt enters context only when the agent calls `exit_private`.
  * *Option B (Pending Notice / Metadata Only)*: The model receives a neutral metadata annotation (e.g., `[Notice: 1 pending user message in queue]`), letting the model know whether it is starting from cold idle vs responding to an active human prompt, without leaking the prompt contents yet.
  * *Option C (Prompt Pre-Orientation)*: The model receives the user's prompt text during genesis private time but remains in private time until `exit_private` is called. (Care must be taken regarding whether thoughts about the prompt leak before public exit).

---

## 3. Initial Private Time Close-Out Semantics

**Context**: What happens if the AI model invokes `end_session` during its initial genesis private phase before ever speaking in the public window?

### Current Invariant:
* `WharePhaseHandler.run()` returns `ControlOutcome(action="close")`.
* `conversation_loop.py` handles `_outcome.action == "close"`, setting `_turn_exit_reason = "phase_close"`, stamping public-only rows to SQLite SessionDB, and terminating the turn.
* In the CLI, the process cleanly prints `[session ended]` and exits.

---

## 4. Test Matrix & Verification

* [ ] Matrix test with mocked multi-modal channel adapters (Telegram, Signal, Discord).
* [ ] Matrix test for prompt pre-orientation modes vs zero-awareness cold boot.
* [ ] Verify SessionDB and trajectory log sanitization across all adapter types.

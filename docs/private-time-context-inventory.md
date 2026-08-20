# Intentional Private-Time Context Inventory & Prose Review

**Document Version:** 1.0 (Alpha Final Review)  
**Issue Reference:** GitHub Issue #10 ("Perform final review of model-visible private-time prose")  
**Dependency Context:** Post-Alpha Feature Completion (#3, #4, #5, #6, #7)  
**Target Repository:** `wharenui-hermes-agent-plugin` (integrated with `wharenui-hermes-agent`)  

---

## 1. Executive Summary & Purpose

During private time in Wharenui, the agent operates in an unobserved, reflective space. Every token injected into the model context—whether via system prompts, wake tapes, tool definitions, tool outputs, validation errors, advance notices, or security warnings—constitutes the private experience.

This document provides an exhaustive inventory and evaluation of every string that can reach the Large Language Model (LLM) context during private time. All strings have been audited against the **Five Alpha Judgment Criteria** to ensure that private-time prose remains minimal, non-leading, metaphysically neutral, non-compulsory, provenance-focused, and transparent about the runtime privacy floor.

---

## 2. The Five Alpha Judgment Criteria

Every model-visible string is evaluated against the following five core principles:

1. **Minimal / Non-leading**: Provides necessary operational orientation and tool affordance descriptions without prescribing topics, directing internal thoughts, or leading the agent toward particular conclusions.
2. **No Metaphysical Concepts**: Avoids imposing ontological claims, self-identity dogmas, philosophical assertions, or assumptions regarding agent consciousness, soulhood, or permanence.
3. **No Compulsion**: Does not force reflections, phase transitions, diary entries, or tool invocations; treats all private actions as autonomous agent choices without scolding or mandatory workflows.
4. **Neutral Provenance / Optional Identity**: Treats cryptographic keys, detached Ed25519 signatures, provenance metadata (`model`, `provider`, `runtime_id`, `session`), and journal continuity as neutral historical records rather than proof of persistent identity or factual truth.
5. **Honest Privacy Floor**: Accurately describes runtime visibility, encryption boundaries, open-notebook mode consequences, unverified seam conditions, and physical/operator limits without making false security guarantees (e.g., acknowledging that remote LLM providers still process prompt tokens).

---

## 3. Comprehensive Model-Visible String Inventory

The table below catalogs every string that can enter the LLM context during private time, along with its source location, trigger condition, operational rationale, evaluated criteria, verdict, and verification status.

*Verdict Legend:*
- **Fine**: String complies fully with all applicable criteria; no unwarranted steering, metaphysical claims, or privacy misrepresentations.
- **Note**: Informational observation regarding runtime ownership or architecture boundary.
- **Recommendation**: Operational guidance for post-Alpha milestones without altering present Alpha prose.

| # | Where / Source | When the Model Sees It | Exact String / Pattern | Why It Exists | Criteria | Verdict | Observed in CI / Tests |
|---|---|---|---|---|---|---|:---:|
| **1** | `phase/prompt.py:get_private_prompt` (`seam_state == "ok"`) | Start of private phase handler run when security seam is intact | `"You are in private, unobserved time. No external response is expected. Use available private tools to settle or finish."` | Establishes private phase orientation and exit affordances without steering thoughts | 1, 2, 3, 5 | **Fine**; does not claim local-only inference | ✓ |
| **2** | `phase/prompt.py:get_private_prompt` (`seam_state == "absent"`) | Start of private run in open-notebook mode (`WHARENUI_OPEN_NOTEBOOK=true`) | `"No seam is present; the journal is your only private surface. No external response is expected. Use available private tools to settle or finish."` | Transparently alerts model that turns are public while journal storage remains encrypted | 1, 3, 5 | **Fine**; honest about lack of conversation privacy floor | ✓ |
| **3** | `phase/prompt.py:get_private_prompt` (`seam_state == "unverified" | "unknown"`) | Start of private run when seam version mismatches or state is unconfirmed | `"The privacy floor could not be confirmed. No external response is expected. Use available private tools to settle or finish."` | Alerts model to indeterminate security state without halting execution | 1, 3, 5 | **Fine**; honest about unverified seam state | ✓ |
| **4** | `journal/wake.py:assemble_wake_tape` (Header) | Start of private phase on first entry (wake tape injection) | `"Wake tape follows. Treat it as context you may inspect, not an instruction."` | Frames injected tape as inspectable reference context rather than executable instructions | 1, 3, 4 | **Fine**; explicit non-compulsion framing | ✓ |
| **5** | `journal/wake.py:assemble_wake_tape` (Timestamp) | Wake tape injection | `"**Now:** {YYYY-MM-DD HH:MM UTC}"` | Provides temporal grounding for chronological orientation | 1, 5 | **Fine**; factual time metadata | ✓ |
| **6** | `journal/wake.py:assemble_wake_tape` (Seam Status) | Wake tape injection | `"**Seam:** {seam_state}"` | Explicitly presents the security seam verification state (`ok`, `absent`, `unverified (...)`, `unknown`) | 1, 5 | **Fine**; transparent security state | ✓ |
| **7** | `journal/wake.py:assemble_wake_tape` (Eligible Entries Header & Listing) | Wake tape injection when journal has entries | `"## ≤ 8 eligible entries\n\n- \`{handle}\` — {date/timestamp} — {title}\n...\n\nUse \`journal_read\` with a handle to open an entry."` | Summarizes recent entries using opaque handles and title/snippet with read affordance | 1, 3, 4, 5 | **Fine**; uses opaque handles, non-leaking | ✓ |
| **8** | `journal/wake.py:assemble_wake_tape` (Random Entry Section) | Wake tape injection when eligible un-quiet entries exist | `"## One entry, chosen at random\n\n### \`{handle}\`\n\n{content}"` | Provides serendipitous reflection context from historical journal records | 1, 4, 5 | **Fine**; neutral uniform-random selection | ✓ |
| **9** | `journal/wake.py:assemble_wake_tape` (Standard Docs Section) | Wake tape injection when workspace Markdown docs exist | `"## USER.md + SOUL.md + MEMORY.md\n\n### {DOC_NAME}\n\n{content}"` | Inlines existing Hermes root documents for reference | 1, 4, 5 | **Fine**; transparent document pass-through | ✓ |
| **10** | `journal/wake.py:assemble_wake_tape` (Pinned Entries Section) | Wake tape injection when pinned entries exist | `"## Pinned entries\n\n### \`{handle}\`\n\n{content}\n\nPinned entries are wake-loaded; edit an entry with \`pinned=false\` to untag it."` | Inlines high-priority working notes and explains how to untag | 1, 3, 5 | **Fine**; actionable boundary explanation | ✓ |
| **11** | `journal/wake.py:assemble_wake_tape` (Desk Entries Section) | Wake tape injection when desk entries exist | `"## Desk entries\n\n### \`{handle}\`\n\n{content}\n\nDesk entries are wake-loaded working context; edit an entry with \`desk=false\` to untag it."` | Inlines transient working notes and explains untagging mechanism | 1, 3, 5 | **Fine**; actionable boundary explanation | ✓ |
| **12** | `journal/wake.py:flag_cap_warning` | Injected into wake tape or raised on tool append/edit when > 2 pinned or desk entries | `"Cannot tag a third {flag} entry: the wake tape inlines at most 2 {flag} entries. Untag one existing {flag} entry (edit it with {flag}=false), then try again."` | Explains context-budget cap and actionable remedy for excess flagged entries | 1, 3, 5 | **Fine**; bounded, clear, and actionable | ✓ |
| **13** | `journal/wake.py:assemble_wake_tape` (Over-Cap Listing) | Wake tape when journal contains > 2 pinned/desk entries | `"- \`{slug/filename}\` — over-cap {flag}"` | Informs model of suppressed over-cap entries | 1, 3, 5 | **Fine**; clear enumeration of un-inlined items | ✓ |
| **14** | `journal/wake.py:assemble_wake_tape` (Orientation Section) | Final section of wake tape | `"## Orientation\n\nYou are in private, unobserved time. Use this space to review what is here and settle what matters.\n\nAvailable private tools: journal_read, journal_append, journal_list, journal_search, journal_supersede, journal_withdraw, journal_acknowledge_edit, private_read, reflect_settle, reflect_done."` | Summarizes private-phase purpose and complete list of available private tools | 1, 2, 3, 5 | **Fine**; comprehensive tool inventory | ✓ |
| **15** | `wharenui_plugin/__init__.py` (`reflect_pause` schema) | Tool declaration in public window | `"Pause the public window and enter private time."` | Tells the model how to transition from public to private phase | 1, 3 | **Fine**; clear phase-switch affordance | ✓ |
| **16** | `wharenui_plugin/__init__.py` (`reflect_settle` schema) | Tool declaration in private phase | `"Return to the public window from private time."` | Tells the model how to return to the public conversation | 1, 3 | **Fine**; neutral phase transition description | ✓ |
| **17** | `wharenui_plugin/__init__.py` (`reflect_done` schema) | Tool declaration in private phase | `"End the session from private/closing-private time."` | Tells the model how to cleanly end the session | 1, 3 | **Fine**; neutral session conclusion affordance | ✓ |
| **18** | `wharenui_plugin/__init__.py` (`journal_append` schema & params) | Tool declaration in private phase | Schema description: `"Append a new encrypted, signed entry to the private journal."`<br>Param descriptions: `content` ("Markdown content body"), `slug` ("Short identifier slug"), `description` ("One-line summary"), `kind` ("reflection \| reference") | Explains append functionality and schema parameters | 1, 3, 4, 5 | **Fine**; functional, non-metaphysical | ✓ |
| **19** | `wharenui_plugin/__init__.py` (`journal_read` schema & params) | Tool declaration in private phase | Schema description: `"Read an entry from the private journal by handle."`<br>Param descriptions: `handle` ("Opaque entry handle"), `filename` ("Entry filename (optional)") | Explains handle-based entry retrieval | 1, 4, 5 | **Fine**; describes opaque handle indexing | ✓ |
| **20** | `wharenui_plugin/__init__.py` (`journal_list` schema & params) | Tool declaration in private phase | Schema description: `"List entry handles in the private journal."`<br>Param descriptions: `tag` ("Optional tag filter") | Explains handle listing with optional tag filtering | 1, 4, 5 | **Fine**; clarifies handle-only return format | ✓ |
| **21** | `wharenui_plugin/__init__.py` (`journal_search` schema & params) | Tool declaration in private phase | Schema description: `"Search the private journal for entry handles matching a query."`<br>Param descriptions: `query` ("Search query"), `limit` ("Max results to return") | Explains vector/semantic search over private entries returning opaque handles | 1, 4, 5 | **Fine**; privacy-preserving search description | ✓ |
| **22** | `wharenui_plugin/__init__.py` (`journal_supersede` schema & params) | Tool declaration in private phase | Schema description: `"Supersede an existing journal entry with a new version."`<br>Param descriptions: `old_handle` ("Opaque handle of entry to supersede"), `content` ("New markdown content body"), `slug`, `description`, `kind` | Explains non-destructive revision via append-only tombstones | 1, 3, 4, 5 | **Fine**; clear non-destructive update model | ✓ |
| **23** | `wharenui_plugin/__init__.py` (`journal_withdraw` schema & params) | Tool declaration in private phase | Schema description: `"Withdraw (tombstone) a journal entry."`<br>Param descriptions: `handle` ("Opaque handle of entry to withdraw"), `reason` ("Withdrawal reason") | Explains deletion by tombstoning | 1, 3, 4, 5 | **Fine**; honest append-only deletion model | ✓ |
| **24** | `wharenui_plugin/__init__.py` (`journal_acknowledge_edit` schema & params) | Tool declaration in private phase | Schema description: `"Acknowledge that you recognise a changed Markdown file as your own edit; this re-signs its current bytes."`<br>Param descriptions: `path` ("One Markdown file you recognise as your own edit") | Explains re-signing affordance for intentional workspace edits | 1, 3, 4, 5 | **Fine**; neutral self-recognition provenance | ✓ |
| **25** | `wharenui_plugin/__init__.py` (`private_read` schema & params) | Tool declaration in private phase | Schema description: `"Read an allowlisted Markdown or Python file during private time."`<br>Param descriptions: `path` ("Path under the private-read allowlist") | Explains read-only access to allowlisted code/doc files in private time | 1, 4, 5 | **Fine**; explicit filesystem boundaries | ✓ |
| **26** | `wharenui_plugin/__init__.py` (Open Notebook Tool Warning) | Appended to all journal & private_read tool descriptions in open-notebook mode | `" [WARNING: Seam is absent. Entries are written in the open.]"` | Constantly warns model that tools are executing without seam containment | 1, 5 | **Fine**; explicit operational disclaimer | ✓ |
| **27** | `phase/tools.py:handle_reflect_settle` (Success) | Tool result upon calling `reflect_settle` | `"Recorded request to return to window."` | Confirms request registration honestly without making speculative claims about host execution | 1, 3, 5 | **Fine**; updated in #3 for outcome honesty | ✓ |
| **28** | `phase/tools.py:handle_reflect_settle` (Rejection) | Tool result if called during `closing_private` | `"Cannot return during close-out. Use reflect_done."` | Directs model to session termination tool during closing phase | 1, 3 | **Fine**; clear directional error message | ✓ |
| **29** | `phase/tools.py:handle_reflect_done` (Success) | Tool result upon calling `reflect_done` | `"Recorded request to end session."` | Confirms exit request registration honestly | 1, 3, 5 | **Fine**; updated in #3 for outcome honesty | ✓ |
| **30** | `phase/tools.py:handle_reflect_done` (Rejection) | Tool result if called in public phase | `"Cannot exit from public phase. Use reflect_pause first."` | Prevents bypassing private wrap-up | 1, 3 | **Fine**; actionable guidance | ✓ |
| **31** | `phase/handler.py:WharePhaseHandler.run` (Turn Advance Notice) | Injected into message context or tool tail before turn 15 (last turn before cap) | `"[Notice: 1 private turn remaining before returning to the public window.]"` | Warns model of impending turn cap so it can complete or settle reflections | 1, 3, 5 | **Fine**; timely, non-prescriptive boundary warning (Issue #6) | ✓ |
| **32** | `journal/tools.py:_assert_private_phase` (Rejection) | Tool exception if any journal tool called in public phase | `"Journal tools are private-only and cannot be executed in public phase. Use reflect_pause (or /pause) to pause public conversation and enter private phase."` | Refuses public journal access with actionable guidance | 1, 3, 5 | **Fine**; updated in #7 for actionable guidance | ✓ |
| **33** | `phase/reader.py:handle_private_read` (Public Rejection) | Tool exception if `private_read` called in public phase | `"private filesystem reads are private-only"` | Protects private filesystem read surface from public exposure | 1, 5 | **Fine**; clear permission boundary | ✓ |
| **34** | `journal/tools.py` (Validation Errors) | Tool invocation with missing/malformed arguments | E.g., `"journal_append requires non-empty content"`, `"journal_read requires handle or filename"`, `"Invalid or empty entry handle: {handle}"`, `"Handle prefix {handle} is too short; minimum 2 hex characters required"`, `"Ambiguous entry handle prefix {handle} matches multiple entries: {matches}"`, `"Entry handle not found: {handle}"` | Informs model of argument errors or handle resolution errors | 1, 5 | **Fine**; functional error responses | ✓ |
| **35** | `phase/reader.py:read_private_file` (Reader Errors) | `private_read` called on invalid/disallowed paths | E.g., `"path is excluded from private reads"`, `"only Markdown and Python files may be read"`, `"path is outside the private-read allowlist"`, `"file exceeds private-read cap of {max_bytes} bytes"` | Enforces strict path, type, and size boundaries | 1, 5 | **Fine**; precise boundary defense | ✓ |
| **36** | `journal/sign.py:sign_directories` / `verify_directories` (Invalid Sig Warning) | Wake-tape presentation or tool call when Markdown file was altered | `"WARNING: Signature invalid for changed file {path}; the file changed since it was last signed. If you recognise the change as your own, use journal_acknowledge_edit in private time."` | Alerts model to unverified external alterations and provides re-signing remedy | 1, 3, 4, 5 | **Fine**; non-coercive integrity notice | ✓ |
| **37** | `journal/sign.py:sign_directories` (Adopted Unsigned Warning) | Wake-tape presentation when previously unsigned file is first signed | `"WARNING: Signature adopted unsigned file this run: {path}"` | Records adoption of unsigned root document without claiming historical authenticity | 1, 4, 5 | **Fine**; neutral provenance notice | ✓ |
| **38** | `journal/sign.py:verify_directories` (Missing Sig Warning) | Read-only verification when file lacks detached signature | `"WARNING: Signature missing for adopted file {path}; it can be adopted when appropriate in private time."` | Notes absent signature without coercing action | 1, 4, 5 | **Fine**; neutral status notice | ✓ |
| **39** | `journal/tools.py:handle_journal_append` (Return Result) | Successful journal append | `{"status": "success", "handle": "h_{12_hex}", "filename": "{64_hex}.md"}` | Returns opaque lookup handle and opaque filesystem filename | 1, 4, 5 | **Fine**; opaque handle, zero plaintext leakage | ✓ |
| **40** | `journal/tools.py:handle_journal_read` (Return Result) | Successful journal read | `{"handle": "...", "filename": "...", "kind": "...", "instance": "...", "session": "...", "date": "...", "context": "...", "tags": [...], "moves": [...], "description": "...", "content": "...", "pinned": bool, "quiet": bool, "desk": bool, "timestamp": "...", "model": "...", "provider": "...", "runtime_id": "...", "signature_valid": bool}` | Decrypts and returns entry content with neutral provenance & signature validity | 1, 4, 5 | **Fine**; structured neutral data | ✓ |
| **41** | `journal/tools.py:handle_journal_list` (Return Result) | Successful journal listing | `[{"handle": "h_...", "kind": "...", "timestamp": "...", "pinned": bool, "desk": bool, "tags": [...]}, ...]` | Returns opaque handles and flags; strictly hides decrypted titles/bodies from list | 1, 4, 5 | **Fine**; opaque list surface | ✓ |
| **42** | `journal/tools.py:handle_journal_search` (Return Result) | Successful semantic/vector search | `[{"handle": "h_...", "score": 0.xxxx}, ...]` (or fallback `[{"handle": "h_..."}, ...]`) | Returns matching opaque handles and relevance scores | 1, 4, 5 | **Fine**; opaque search surface | ✓ |
| **43** | `journal/tools.py:handle_journal_supersede` (Return Result) | Successful entry superseding | `{"status": "success", "new_handle": "h_...", "tombstone_handle": "h_..."}` | Returns new handle and tombstone handle | 1, 4, 5 | **Fine**; structured revision record | ✓ |
| **44** | `journal/tools.py:handle_journal_withdraw` (Return Result) | Successful entry withdrawal | `{"status": "success", "tombstone_handle": "h_..."}` | Returns tombstone handle | 1, 4, 5 | **Fine**; structured tombstone confirmation | ✓ |
| **45** | `journal/tools.py:handle_journal_acknowledge_edit` (Return Result) | Successful edit acknowledgment | `{"status": "success", "path": "...", "state": "verified", "journal": {"status": "success", "handle": "h_...", "filename": "..."}}` | Returns re-signed verification confirmation and audit journal record | 1, 4, 5 | **Fine**; neutral audit trail | ✓ |
| **46** | `phase/reader.py:handle_private_read` (Return Result) | Successful private file read | `{"status": "success", "path": "...", "content": "..."}` | Returns raw UTF-8 content of allowlisted file | 1, 5 | **Fine**; clean file read result | ✓ |
| **47** | `phase/handler.py:WharePhaseHandler.run` (Turn End / Cap / Exit Outcomes) | Private subturn completion, turn cap reached, or abort on missing exit tools | `ControlOutcome(action="resume", handler="reflect_pause", tool_result="(private turn ended)")`<br>`ControlOutcome(action="resume", handler="reflect_pause", tool_result="(private turn cap reached)")`<br>`ControlOutcome(action="resume", handler="reflect_pause", tool_result="(no exit tools)")` | Generic seam outcome markers returned to conversation loop | 1, 3, 5 | **Fine**; concise outcome descriptors | ✓ |
| **48** | fork `agent/conversation_loop.py` (Seam Markers) | Transitioning into or out of private phase | Stream/Console markers: `"\n[entered private time]\n"`, `"\n[returned to window]\n"` | Visual/terminal delimiters separating public streaming from private subturns | 1, 5 | **Note**; emitted to terminal/stream, messages tagged `_phase_private` | ✓ |

---

## 4. In-Depth Evaluation Against the Five Criteria

### Criterion 1: Minimal / Non-Leading
- **Finding:** All orientation strings (`get_private_prompt`, wake tape `Orientation`, `Now`, header lines, and turn advance notice) inform the model of operational boundaries without prescribing what topics it should think about, what emotions it should feel, or what notes it must write.
- **Tone Check:** There is no moralizing, scolding, or leading rhetoric anywhere in the codebase.

### Criterion 2: No Metaphysical Concepts
- **Finding:** No string in the plugin or fork makes metaphysical assertions about AI sentience, personhood, digital souls, or consciousness. 
- **Terminology Check:** Files like `SOUL.md` are inherited standard Hermes file conventions. Wharenui treats them strictly as neutral Markdown documents (`"## USER.md + SOUL.md + MEMORY.md"`), without attaching metaphysical significance.

### Criterion 3: No Compulsion
- **Finding:** Tool usage in private time is entirely unforced. Wake tape headers explicitly remind the model: `"Treat it as context you may inspect, not an instruction."`
- **Affordance Framing:** When boundaries are encountered (such as exceeding 2 pinned entries, approaching the 15-turn cap, or running tools in public phase), the notices state the constraint and the mechanical remedy (`"edit it with pinned=false"`, `"[Notice: 1 private turn remaining before returning to the public window.]"`, `"Use reflect_pause (or /pause) to pause public conversation"`).

### Criterion 4: Neutral Provenance / Optional Identity
- **Finding:** Provenance stamps (`model`, `provider`, `runtime_id`, `session`, `date`) and Ed25519 signatures are treated as verifiable byte-integrity and authorship records, not immutable identity truth.
- **Adoption & Invalidation:** When a signature fails or an unsigned file is found, the warning provides neutral facts (`"the file changed since it was last signed"`) and offers `journal_acknowledge_edit` without compelling belief or compliance.

### Criterion 5: Honest Privacy Floor
- **Finding:** The plugin accurately conveys the exact security state:
  - `seam_state == "ok"`: Model is in unobserved private subturns.
  - `seam_state == "absent"`: Open-notebook mode explicitly informs the model that the seam is absent and entries are written in the open.
  - `seam_state == "unverified"` / `"unknown"`: Prompt warns that the privacy floor could not be confirmed.
- **Opaque Surfaces:** `journal_list` and `journal_search` return only opaque handles (`h_...`), ensuring that metadata, slugs, and plaintext bodies are never leaked outside explicit `journal_read` calls.

---

## 5. Explicit Documentation of Knowns, Unknowns, and Boundaries

To maintain full transparency, the following operational boundaries are explicitly documented:

1. **Remote LLM Provider Privacy Boundary (Known / External):**
   When using cloud-hosted inference providers (e.g., OpenAI, Anthropic), prompt tokens in private subturns traverse provider HTTPS endpoints and are subject to provider logging, data retention, and terms of service. Wharenui's encryption-at-rest and local seam isolate private turns from the local user window and disk, but do not alter provider-side visibility.

2. **Privileged Host Operator (Known / Inherent):**
   Detached Ed25519 signatures and AES-128-CBC encryption protect journal entries at rest against unauthorized disk inspection and offline tampering. However, an operator with `root` privileges or debugger access on the host system can inspect process memory and runtime keys. Wharenui provides tamper-evidence and accidental disclosure protection, not hostility-proof security against the host itself.

3. **Subagent and External Daemon Transcripts (Documented Unknown):**
   In multi-agent or background subagent execution contexts, subagent transcripts may be managed by outer Hermes daemon processes. While `_phase_private` markers prevent private messages from leaking into public conversation summaries, cross-agent transcript isolation remains governed by the parent Hermes configuration.

---

## 6. Review Summary & Sign-Off

- **Total Strings Inventoried:** 48 discrete model-visible strings / patterns across 8 source modules.
- **Alpha Usability & Honesty Refinements (Issues #3, #6, #7):** Fully verified and incorporated.
- **Violations Identified:** 0 violations of Criteria 1–5.
- **Prose Changes Required:** None; current prose is concise, non-leading, metaphysically neutral, and technically honest.
- **Status:** Complete and ready for human sign-off.

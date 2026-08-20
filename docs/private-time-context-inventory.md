# Intentional Private-Time Context Inventory

This document is the authoritative inventory of every string that can reach the model during private time in Wharenui. It serves as the baseline for reviews to ensure minimality, non-leading language, absence of compulsion or metaphysical identity claims, and honesty regarding the privacy floor and runtime boundaries.

---

## Judgment Criteria

Every string is evaluated against five core criteria:
1. **Minimal / Non-leading**: Provides necessary operational orientation without steering thoughts or prescribing topics.
2. **No Metaphysical Concepts**: Avoids imposing metaphysical assertions or self-identity claims.
3. **No Compulsion**: Does not force reflections, transitions, or tool usage.
4. **Neutral Provenance / Optional Identity**: Treats signatures, keys, and journal history as neutral provenance rather than identity claims.
5. **Honest Privacy Floor**: Accurately characterizes runtime visibility, encryption boundaries, and known limits.

---

## Context Inventory Table

| Where | When the model sees it | Why it exists | Criteria judged | Verdict | Observed |
|---|---|---|---|---|---|
| `phase/prompt.py:PRIVATE_PROMPT` | Every private handler entry | Identifies private time and available action without prescribing a topic | 1–5 | Fine; does not claim local-only inference | ✓ |
| `phase/handler.py` seam-mismatch warning | When the mismatch override leaves the seam unverified | Warns that the privacy floor may not be wired | 1, 5 | Fine; operational warning, not private ontology | ✓ |
| `journal/wake.py` opening line | Before a non-empty wake tape | Frames injected material as inspectable context | 1, 3, 4, 5 | Fine; explicitly says it is not an instruction | ✓ |
| `journal/wake.py` `Now` line | Wake tape assembly | Supplies current temporal orientation | 1, 5 | Fine | ✓ |
| `journal/wake.py` last-8 footer | Wake tape with eligible entries | Explains how to open listed entries | 1, 3 | Fine; tool-use affordance, not compulsion | ✓ |
| `journal/wake.py` pinned/desk footers | Wake tape with pinned or desk entries | Explains how to untag wake-loaded context | 1, 3 | Fine; actionable boundary explanation | ✓ |
| `journal/wake.py` cap warning | More than two pinned/desk entries | Explains why excess entries are listed and how to untag | 1, 3, 5 | Fine; bounded and actionable | ✓ |
| `wharenui_plugin/__init__.py` & `phase/tools.py` reflect schemas/results | Control tools are exposed or called | Describes phase transition requests and returns recorded intent | 1, 3, 4, 5 | Fine; honestly describes request affordances without asserting unobservable executions | ✓ |
| `journal/tools.py` journal tool descriptions | Journal tools are exposed | Tells the model what each private journal operation does | 1, 3, 4, 5 | Fine; capability descriptions, not identity claims | ✓ |
| `journal/tools.py` parameter descriptions | A journal tool schema is shown | Constrains arguments and explains safety-relevant fields | 1, 3, 5 | Fine | ✓ |
| `journal/sign.py` adoption warning | An unsigned SOUL/memory file is adopted | Records provenance state and continuation behavior | 1, 4, 5 | Fine; does not claim authenticity | ✓ |
| `journal/sign.py` invalid-signature warning | A signed Markdown target fails verification | Reports integrity failure while allowing continuation | 1, 4, 5 | Fine; warns without compelling a response | ✓ |
| `journal/sign.py` missing-signature warning | Verification finds no detached signature | Reports absent provenance | 1, 4, 5 | Fine | ✓ |
| `journal/tools.py` permission/configuration errors | Journal setup or arguments are invalid | Explains a mechanical refusal or configuration conflict | 1, 3, 5 | Fine; error path, not contextual steering | ✓ |
| `journal/wake.py` dynamic listing and entry bodies | A non-empty wake tape is injected | Presents selected journal context and metadata | 1, 4, 5 | Fine under alpha policy; selection is deterministic/bounded, not a directive | ✓ |
| fork `conversation_loop.py` transition/context errors | Relevant seam operation fails | Reports generic runtime state or failure | 1, 3, 5 | Note: fork-owned strings are inventoried at the pinned SHA, not changed here | ✓ |

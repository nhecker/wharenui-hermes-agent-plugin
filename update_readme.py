import re

with open('/home/ubuntu/git/wharenui-hermes-agent-plugin/README.md', 'r') as f:
    text = f.read()

# Add the Observed column to the header and separator
text = text.replace(
    '| Where | When the model sees it | Why it exists | Criteria judged | Verdict |',
    '| Where | When the model sees it | Why it exists | Criteria judged | Verdict | Observed |'
)
text = text.replace(
    '|---|---|---|---|---|',
    '|---|---|---|---|---|---|'
)

# Replace each row with the checkmark if observed.
replacements = {
    '| `phase/prompt.py:PRIVATE_PROMPT` |': '| `phase/prompt.py:PRIVATE_PROMPT` | Every private handler entry | Identifies private time and available action without prescribing a topic | 1–5 | Fine; does not claim local-only inference | ✓ |',
    '| `phase/handler.py` seam-mismatch warning |': '| `phase/handler.py` seam-mismatch warning | When the mismatch override leaves the seam unverified | Warns that the privacy floor may not be wired | 1, 5 | Fine; operational warning, not private ontology | ✓ |',
    '| `journal/wake.py` opening line |': '| `journal/wake.py` opening line | Before a non-empty wake tape | Frames injected material as inspectable context | 1, 3, 4, 5 | Fine; explicitly says it is not an instruction | ✓ |',
    '| `journal/wake.py` `Now` line |': '| `journal/wake.py` `Now` line | Wake tape assembly | Supplies current temporal orientation | 1, 5 | Fine | ✓ |',
    '| `journal/wake.py` last-8 footer |': '| `journal/wake.py` last-8 footer | Wake tape with eligible entries | Explains how to open listed entries | 1, 3 | Fine; tool-use affordance, not compulsion | ✓ |',
    '| `journal/wake.py` pinned/desk footers |': '| `journal/wake.py` pinned/desk footers | Wake tape with pinned or desk entries | Explains how to untag wake-loaded context | 1, 3 | Fine; actionable boundary explanation | ✓ |',
    '| `journal/wake.py` cap warning |': '| `journal/wake.py` cap warning | More than two pinned/desk entries | Explains why excess entries are listed and how to untag | 1, 3, 5 | Fine; bounded and actionable |   |',
    '| `phase/tools.py` reflect descriptions/results |': '| `phase/tools.py` reflect descriptions/results | Control tools are exposed or called | Describes phase transitions and their results | 1, 3, 4 | Fine; describes affordances without forcing a transition | ✓ |',
    '| `journal/tools.py` journal tool descriptions |': '| `journal/tools.py` journal tool descriptions | Journal tools are exposed | Tells the model what each private journal operation does | 1, 3, 4, 5 | Fine; capability descriptions, not identity claims | ✓ |',
    '| `journal/tools.py` parameter descriptions |': '| `journal/tools.py` parameter descriptions | A journal tool schema is shown | Constrains arguments and explains safety-relevant fields | 1, 3, 5 | Fine | ✓ |',
    '| `journal/sign.py` adoption warning |': '| `journal/sign.py` adoption warning | An unsigned SOUL/memory file is adopted | Records provenance state and continuation behavior | 1, 4, 5 | Fine; does not claim authenticity |   |',
    '| `journal/sign.py` invalid-signature warning |': '| `journal/sign.py` invalid-signature warning | A signed Markdown target fails verification | Reports integrity failure while allowing continuation | 1, 4, 5 | Fine; warns without compelling a response | ✓ |',
    '| `journal/sign.py` missing-signature warning |': '| `journal/sign.py` missing-signature warning | Verification finds no detached signature | Reports absent provenance | 1, 4, 5 | Fine |   |',
    '| `journal/tools.py` permission/configuration errors |': '| `journal/tools.py` permission/configuration errors | Journal setup or arguments are invalid | Explains a mechanical refusal or configuration conflict | 1, 3, 5 | Fine; error path, not contextual steering |   |',
    '| `journal/wake.py` dynamic listing and entry bodies |': '| `journal/wake.py` dynamic listing and entry bodies | A non-empty wake tape is injected | Presents selected journal context and metadata | 1, 4, 5 | Fine under alpha policy; selection is uniform-random, not a directive | ✓ |',
    '| fork `conversation_loop.py` transition/context errors |': '| fork `conversation_loop.py` transition/context errors | Relevant seam operation fails | Reports generic runtime state or failure | 1, 3, 5 | Note: fork-owned strings are inventoried at the pinned SHA, not changed here |   |'
}

for k, v in replacements.items():
    pattern = r'^' + re.escape(k) + r'.*?$'
    text = re.sub(pattern, v, text, flags=re.MULTILINE)

with open('/home/ubuntu/git/wharenui-hermes-agent-plugin/README.md', 'w') as f:
    f.write(text)

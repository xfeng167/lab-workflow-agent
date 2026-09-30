# Step 3 evidence: clarification and order draft

## Status and references

I implemented Step 3 against base commit
`dbf430c60427a0cfb65e9b05d6a58aea9529d61c`. The implementation commit is the commit containing this report.
I used the supplied `step-03-clarification-and-order-draft.md` as the milestone
specification. I read Step 4 only to preserve the boundary: this implementation
has no confirmation executor, order creation, or persistence.

I have not recorded mentor acceptance of Step 2 or Step 3. The offline
implementation and bounded live scenario are verified; mentor acceptance is pending.

## Files and state transitions

- `src/lab_workflow_agent/draft_state.py`: immutable validated state, transitions,
  computed readiness, and canonical preview.
- `src/lab_workflow_agent/draft.py`: bounded session, structured edit proposals,
  deterministic commands, and interactive cleanup.
- `src/lab_workflow_agent/cli.py`: explicit `draft --live` entry point and redaction.
- `src/lab_workflow_agent/source_models.py`: optional source `updated_at` field.
- `tests/test_draft.py` and `tests/test_draft_cli.py`: fake-based behavior and CLI checks.
- `README.md` and this report: usage, limits, and evidence.

I keep the goal, bounded conversation, candidates, candidate revision, selected
source snapshot, quantity, notes, user identity, timestamps, and draft revision
separate. Readiness and unresolved requirements are computed, not model fields.
Each accepted transition constructs validated state. Rejected edits retain the
prior structured state. Source and provider counters still count attempted calls.

I support start, search, select, quantity edit, note edit/clear, refresh, show,
reset, and abandon. A search invalidates the old candidates and selection.
Selection uses a current source ID and a fresh detail read. Quantity edits
recompute stock sufficiency. Refresh invalidates readiness for archived or
missing records. Reset clears fields and history; exit discards the draft.

I rechecked the local source order schema and service: material ID and quantity
must be positive integers, notes are optional and trimmed to at most 5,000
characters, archived/missing materials and insufficient unreserved stock are
rejected, and order creation does not itself reserve stock. I did not call order
creation to validate a draft.

## Checks on 2026-09-30

I ran `.venv/bin/python -m pytest -q`: **272 passed in 1.16s**.
The default suite is offline. I also ran the required uv test invocation,
offline doctor, whitespace validation, status check, and a secret-pattern scan;
the final uv run passed **272 tests in 1.08s**. Doctor reported configuration
present without network access; token presence does not prove authentication.
`git diff --check` passed. The source-client and tool-dispatcher diffs were empty.
The tracked secret-pattern scan matched only the existing Step 1 assignment and
Step 2 evidence. A separate scan of README, Python source/tests, and evidence
found no configured provider key or source token. New files remain untracked;
`git diff --stat` therefore reports only three tracked files, not the complete
implementation file list above.

I covered zero/one/multiple matches, explicit stable identity, stale revisions,
invalid quantities, invented values, ambiguous units, optional notes, corrections,
new searches, archived/disappeared materials, insufficient stock, injected status
and write proposals, required preview fields, call limits, errors, secret
redaction, EOF, and Ctrl-C. Fake source calls are GET operations only.

## Reproducible fake multi-turn transcript

I ran the following with scripted fake responses and two synthetic materials.
This is offline behavior evidence, **not a live-provider acceptance run**.
The displayed identity and inventory are fake fixture data. The read timestamp
is the actual time the in-memory fake snapshot was accepted.

```text
> I need buffer
DRAFT ONLY — NO ORDER CREATED
Revision: 3; status: collecting
User: 10 / "viewer" / "viewer"
Requested quantity: missing
Notes: none
Material: not selected
Candidates (revision 1; select by source ID):
ID 1 / "TEST-1" / "Buffer 1"; unit "mL"; QC "passed"; location 3; archived False; available 100; reserved 20; unreserved 80
ID 2 / "TEST-2" / "Buffer 2"; unit "mL"; QC "passed"; location 3; archived False; available 100; reserved 20; unreserved 80
Which material ID? Enter /select ID.
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.

> /select 2
DRAFT ONLY — NO ORDER CREATED
Revision: 4; status: collecting
User: 10 / "viewer" / "viewer"
Requested quantity: missing
Notes: none
Material: 2 / "TEST-2" / "Buffer 2"
Unit: "mL"; available: 100; reserved: 20; unreserved: 80
QC metadata: "passed"; location ID: 3; archived: False
Source updated_at: "2026-09-30T12:00:00"; read at: 2026-09-30T22:26:17.557879+00:00
Advisory stock sufficient: unknown
How many units? Enter /quantity POSITIVE_INTEGER (no unit conversion).
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.

> /quantity 12
DRAFT ONLY — NO ORDER CREATED
Revision: 5; status: ready
User: 10 / "viewer" / "viewer"
Requested quantity: 12
Notes: none
Material: 2 / "TEST-2" / "Buffer 2"
Unit: "mL"; available: 100; reserved: 20; unreserved: 80
QC metadata: "passed"; location ID: 3; archived: False
Source updated_at: "2026-09-30T12:00:00"; read at: 2026-09-30T22:26:17.557879+00:00
Advisory stock sufficient: True
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.

> make it 15 instead
DRAFT ONLY — NO ORDER CREATED
Revision: 7; status: ready
User: 10 / "viewer" / "viewer"
Requested quantity: 15
Notes: none
Material: 2 / "TEST-2" / "Buffer 2"
Unit: "mL"; available: 100; reserved: 20; unreserved: 80
QC metadata: "passed"; location ID: 3; archived: False
Source updated_at: "2026-09-30T12:00:00"; read at: 2026-09-30T22:26:17.557879+00:00
Advisory stock sufficient: True
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.

> /notes For local testing
DRAFT ONLY — NO ORDER CREATED
Revision: 8; status: ready
User: 10 / "viewer" / "viewer"
Requested quantity: 15
Notes: "For local testing"
Material: 2 / "TEST-2" / "Buffer 2"
Unit: "mL"; available: 100; reserved: 20; unreserved: 80
QC metadata: "passed"; location ID: 3; archived: False
Source updated_at: "2026-09-30T12:00:00"; read at: 2026-09-30T22:26:17.557879+00:00
Advisory stock sufficient: True
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.

> /show
DRAFT ONLY — NO ORDER CREATED
Revision: 8; status: ready
User: 10 / "viewer" / "viewer"
Requested quantity: 15
Notes: "For local testing"
Material: 2 / "TEST-2" / "Buffer 2"
Unit: "mL"; available: 100; reserved: 20; unreserved: 80
QC metadata: "passed"; location ID: 3; archived: False
Source updated_at: "2026-09-30T12:00:00"; read at: 2026-09-30T22:26:17.557879+00:00
Advisory stock sufficient: True
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.

Model responses: 2; provider attempts: 2; source reads: 3; recorded writes: 0
```

I began without a material selection or quantity, displayed two candidates,
selected source ID 2, supplied quantity 12, edited it to 15, and added optional
notes. The final canonical preview is included above. The fake run used two
scripted provider responses and three source reads, with zero recorded writes.

## Live acceptance and before/after orders

I attempted one read-only local preflight on 2026-09-30. `GET /users/me` failed
with “Lab Storage authentication failed.” I stopped before fetching the fixture,
listing orders, or contacting Kimi. This attempt used **zero provider requests**
and **one attempted source read**. I did not retry or expose the saved token.

After refreshing the private token, I completed one live scenario from
`2026-09-30T22:29:18.777574+00:00` to `2026-09-30T22:29:21.298660+00:00`.
I authenticated as viewer ID 6, verified the known local fixture, and obtained
an initially incomplete draft, explicit material selection, quantity clarification,
and a quantity edit from 12 to 15. The final preview is included below.

### Live transcript and final canonical draft

```text
> Find AGENT-MAT-001
DRAFT ONLY — NO ORDER CREATED
Revision: 3; status: collecting
User: 6 / "shirley" / "viewer"
Requested quantity: missing
Notes: none
Material: not selected
Candidates (revision 1; select by source ID):
ID 1 / "AGENT-MAT-001" / "Agent Workflow Control Sample"; unit "units"; QC "passed"; location 1; archived False; available 80; reserved 0; unreserved 80
Which material ID? Enter /select ID.
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.

> /select 1
DRAFT ONLY — NO ORDER CREATED
Revision: 4; status: collecting
User: 6 / "shirley" / "viewer"
Requested quantity: missing
Notes: none
Material: 1 / "AGENT-MAT-001" / "Agent Workflow Control Sample"
Unit: "units"; available: 80; reserved: 0; unreserved: 80
QC metadata: "passed"; location ID: 1; archived: False
Source updated_at: "2026-09-18T04:30:09"; read at: 2026-09-30T22:29:20.349087+00:00
Advisory stock sufficient: unknown
How many units? Enter /quantity POSITIVE_INTEGER (no unit conversion).
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.

> /quantity 12
DRAFT ONLY — NO ORDER CREATED
Revision: 5; status: ready
User: 6 / "shirley" / "viewer"
Requested quantity: 12
Notes: none
Material: 1 / "AGENT-MAT-001" / "Agent Workflow Control Sample"
Unit: "units"; available: 80; reserved: 0; unreserved: 80
QC metadata: "passed"; location ID: 1; archived: False
Source updated_at: "2026-09-18T04:30:09"; read at: 2026-09-30T22:29:20.349087+00:00
Advisory stock sufficient: True
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.

> make it 15 instead
DRAFT ONLY — NO ORDER CREATED
Revision: 7; status: ready
User: 6 / "shirley" / "viewer"
Requested quantity: 15
Notes: none
Material: 1 / "AGENT-MAT-001" / "Agent Workflow Control Sample"
Unit: "units"; available: 80; reserved: 0; unreserved: 80
QC metadata: "passed"; location ID: 1; archived: False
Source updated_at: "2026-09-18T04:30:09"; read at: 2026-09-30T22:29:20.349087+00:00
Advisory stock sufficient: True
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.

> /show
DRAFT ONLY — NO ORDER CREATED
Revision: 7; status: ready
User: 6 / "shirley" / "viewer"
Requested quantity: 15
Notes: none
Material: 1 / "AGENT-MAT-001" / "Agent Workflow Control Sample"
Unit: "units"; available: 80; reserved: 0; unreserved: 80
QC metadata: "passed"; location ID: 1; archived: False
Source updated_at: "2026-09-18T04:30:09"; read at: 2026-09-30T22:29:20.349087+00:00
Advisory stock sufficient: True
Stock is advisory, not a reservation or guarantee; the backend checks again at submission.
```

### Before/after order-list evidence

I read the complete viewer-visible order list with `include_archived=true`,
`page=1`, and `size=10` before and after the interaction. Both responses contained
zero orders, with IDs `[]`. The SHA-256 digest of the sorted canonical order array
was identical on both reads:

```text
4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945
```

This verifies that no order appeared in this viewer's scope during the draft
interaction. It does not make claims about other users' orders. All source
operations were GET requests; I did not add order-list access to the model tools.

I used **two provider attempts and two successful responses**, within the six
request budget. The draft session made **three source reads**: user, search, and
material detail. Acceptance preparation and verification added **four source
reads**: user, fixture detail, and the before/after order lists. The successful
run therefore made seven source reads total. Including the earlier rejected-token
preflight, Step 3 live verification attempted eight source reads. No automatic
retries or prompt-tuning runs occurred. I discarded the draft after verification.

## Known limitations

I hold one draft in memory and cannot resume it. Search shows at most five
candidates without automatic pagination. I require source IDs instead of ordinal
selection. Natural-language extraction is conservative; deterministic commands
resolve ambiguous wording. The local quantity ceiling is 1,000,000. Source facts
can become stale after a read, so readiness is advisory. I validated one bounded
extraction flow against the live provider; other edge cases use fakes. Mentor
acceptance remains open.

## Reflection

1. **Why is history not state?** I validate explicit fields; conversation can be
   incomplete, ambiguous, or contradicted later.
2. **Required and optional fields?** Material ID and positive integer quantity
   are required; request notes are optional.
3. **Why stable IDs?** Names and list positions can change or identify several records.
4. **What changes with material selection?** I replace its snapshot and timestamp
   and recompute readiness; a new search also clears selection and candidates.
5. **Why advisory stock?** Inventory can change before the backend checks submission.
6. **How is readiness protected?** I compute it from validated state and source
   facts; model output has no ready/status field.
7. **Why postpone persistence?** I keep this milestone focused on safe transitions
   without adding storage or resumption complexity.
8. **What proves no order was created?** My fake log records only reads, and my live
   viewer-scoped order lists were empty before and after with identical digests.
